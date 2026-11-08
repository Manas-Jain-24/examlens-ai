"""Portable JSON backups. Restore makes new copies and never overwrites history."""
from datetime import datetime, timezone
import json
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from backend.core.config import settings
from backend.evaluation import EvaluationExample
from backend.models import AuditReport, ReviewedDraft, QuestionPaper
from backend.storage import database

router = APIRouter(prefix='/backups', tags=['Backup and restore'])

class BackupRevision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    note: str = Field(default='', max_length=2000)
    created_at: datetime
    report: AuditReport

    @model_validator(mode='after')
    def valid_report_context(self):
        if self.report.syllabus:
            ReviewedDraft(syllabus=self.report.syllabus, pyqs=self.report.pyqs, rules=self.report.rules,
                paper=QuestionPaper(paper_title=self.title, course_code=self.report.syllabus.course_code,
                    total_marks=sum(q.marks for q in self.report.mapped_questions),
                    questions=self.report.mapped_questions, choice_groups=self.report.choice_groups))
        return self

class BackupAudit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_id: str = Field(min_length=1)
    revisions: list[BackupRevision] = Field(min_length=1, max_length=10000)

    @model_validator(mode='after')
    def consecutive_revisions(self):
        if [r.revision for r in self.revisions] != list(range(1, len(self.revisions) + 1)):
            raise ValueError('Backup revisions must be ordered and consecutive, starting at 1.')
        return self

class BackupBundle(BaseModel):
    model_config = ConfigDict(extra='forbid')
    format: Literal['examlens-backup'] = 'examlens-backup'
    version: Literal[1] = 1
    exported_at: datetime
    audits: list[BackupAudit] = Field(default_factory=list, max_length=10000)
    evaluation_examples: list[EvaluationExample] = Field(default_factory=list, max_length=10000)

    @model_validator(mode='after')
    def unique_records(self):
        if len({a.source_id for a in self.audits}) != len(self.audits):
            raise ValueError('Audit source IDs must be unique.')
        if len({e.example_id for e in self.evaluation_examples}) != len(self.evaluation_examples):
            raise ValueError('Evaluation example IDs must be unique.')
        return self

@router.get('/export')
def export_backup():
    audits = {}
    with database() as connection:
        for row in connection.execute('SELECT * FROM revisions ORDER BY audit_id, revision'):
            audits.setdefault(row['audit_id'], []).append(BackupRevision(
                revision=row['revision'], title=row['title'], note=row['note'], created_at=row['created_at'],
                report=AuditReport(**json.loads(row['report']))))
        examples = [EvaluationExample(**json.loads(row['payload']))
                    for row in connection.execute('SELECT payload FROM evaluation_examples ORDER BY example_id')]
    bundle = BackupBundle(exported_at=datetime.now(timezone.utc),
        audits=[BackupAudit(source_id=key, revisions=value) for key, value in audits.items()],
        evaluation_examples=examples)
    return Response(content=bundle.model_dump_json(indent=2), media_type='application/json',
        headers={'Content-Disposition': 'attachment; filename="examlens-backup.json"', 'Cache-Control': 'no-store'})

@router.post('/restore')
async def restore_backup(file: UploadFile = File(...)):
    limit = settings.MAX_BACKUP_SIZE_MB * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f'Backup exceeds the {settings.MAX_BACKUP_SIZE_MB}MB limit.')
    try:
        bundle = BackupBundle.model_validate_json(data)
    except ValidationError:
        raise HTTPException(422, 'Invalid or unsupported backup. Check its format, revision sequence, reports, and reference labels.')
    audit_map, example_map = {}, {}
    # All objects are validated before a single transactional write begins.
    with database() as connection:
        connection.execute('BEGIN IMMEDIATE')
        for audit in bundle.audits:
            target_id = str(uuid4())
            audit_map[audit.source_id] = target_id
            for revision in audit.revisions:
                connection.execute('INSERT INTO revisions VALUES (?, ?, ?, ?, ?, ?)', (
                    target_id, revision.revision, revision.title, revision.note,
                    revision.created_at.isoformat(), revision.report.model_dump_json()))
        for example in bundle.evaluation_examples:
            new_id = f'restored_{uuid4().hex}_{example.example_id[:50]}'
            example_map[example.example_id] = new_id
            restored = example.model_copy(update={'example_id': new_id})
            connection.execute('INSERT INTO evaluation_examples VALUES (?, ?)', (new_id, restored.model_dump_json()))
    return {'audits_restored': len(audit_map), 'revisions_restored': sum(len(a.revisions) for a in bundle.audits),
            'examples_restored': len(example_map), 'audit_id_map': audit_map, 'example_id_map': example_map,
            'message': 'Restored as new copies. Existing audits and examples were preserved.'}
