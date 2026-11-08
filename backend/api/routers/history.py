from datetime import datetime, timezone
import json
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from backend.models import AuditReport
from backend.storage import database

router = APIRouter(prefix='/history', tags=['Audit history'])


class SaveRevision(BaseModel):
    report: AuditReport
    audit_id: str | None = None
    expected_revision: int = Field(default=0, ge=0)
    title: str = Field(min_length=1, max_length=200)
    note: str = Field(default='', max_length=2000)


def load_report(connection, audit_id, revision):
    row = connection.execute('SELECT * FROM revisions WHERE audit_id=? AND revision=?',
                             (audit_id, revision)).fetchone()
    if row is None:
        raise HTTPException(404, 'Audit revision not found.')
    return dict(row, report=json.loads(row['report']))


@router.post('')
def save_revision(request: SaveRevision):
    audit_id = request.audit_id or str(uuid4())
    with database() as connection:
        connection.execute('BEGIN IMMEDIATE')
        latest = connection.execute('SELECT MAX(revision) FROM revisions WHERE audit_id=?',
                                    (audit_id,)).fetchone()[0] or 0
        if request.audit_id and not latest:
            raise HTTPException(404, 'Audit not found. Save it as a new audit.')
        if latest != request.expected_revision:
            raise HTTPException(409, 'A newer revision exists. Reopen the latest revision before saving.')
        connection.execute('INSERT INTO revisions VALUES (?, ?, ?, ?, ?, ?)', (
            audit_id, latest + 1, request.title.strip(), request.note,
            datetime.now(timezone.utc).isoformat(), request.report.model_dump_json()))
    return {'audit_id': audit_id, 'revision': latest + 1}


@router.get('')
def list_audits():
    with database() as connection:
        rows = connection.execute('''SELECT r.audit_id, r.revision, r.title, r.note, r.created_at
            FROM revisions r JOIN (SELECT audit_id, MAX(revision) AS revision FROM revisions GROUP BY audit_id) latest
            USING (audit_id, revision) ORDER BY r.created_at DESC LIMIT 200''').fetchall()
    return [dict(row) for row in rows]


@router.get('/{audit_id}/revisions')
def revisions(audit_id: str):
    with database() as connection:
        rows = connection.execute('SELECT audit_id, revision, title, note, created_at FROM revisions WHERE audit_id=? ORDER BY revision DESC',
                                  (audit_id,)).fetchall()
    return [dict(row) for row in rows]


@router.get('/{audit_id}/compare')
def compare(audit_id: str, before: int, after: int):
    with database() as connection:
        old = load_report(connection, audit_id, before)['report']
        new = load_report(connection, audit_id, after)['report']
    old_q = {q['question_id']: q for q in old['mapped_questions']}
    new_q = {q['question_id']: q for q in new['mapped_questions']}
    fields = ['question_text', 'marks', 'mapped_unit', 'unit_allocations', 'blooms_level', 'is_out_of_syllabus', 'review_status', 'review_note']
    changes = []
    for qid in sorted(old_q.keys() | new_q.keys()):
        a, b = old_q.get(qid), new_q.get(qid)
        if a is None or b is None:
            changes.append({'question_id': qid, 'kind': 'added' if a is None else 'removed', 'before': a, 'after': b})
        else:
            changed = {key: {'before': a.get(key), 'after': b.get(key)} for key in fields if a.get(key) != b.get(key)}
            if changed:
                changes.append({'question_id': qid, 'kind': 'changed', 'fields': changed})
    old_findings = {f['finding_id']: f for f in old['findings']}
    new_findings = {f['finding_id']: f for f in new['findings']}
    return {
        'before': before, 'after': after,
        'score_delta': round(new['overall_quality_score'] - old['overall_quality_score'], 2),
        'component_deltas': {key: round(value - old['score_breakdown'][key], 2) for key, value in new['score_breakdown'].items()},
        'questions': changes,
        'resolved_findings': [v['title'] for k, v in old_findings.items() if k not in new_findings],
        'new_findings': [v['title'] for k, v in new_findings.items() if k not in old_findings],
        'changed_findings': [v['title'] for k, v in new_findings.items() if k in old_findings and v != old_findings[k]],
        'rules_changed': old.get('rules') != new.get('rules'),
        'choices_changed': old.get('choice_groups') != new.get('choice_groups'),
        'syllabus_changed': old.get('syllabus') != new.get('syllabus'),
    }


@router.get('/{audit_id}/revisions/{revision}')
def get_revision(audit_id: str, revision: int):
    with database() as connection:
        return load_report(connection, audit_id, revision)
