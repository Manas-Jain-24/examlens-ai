// Document correction, immutable revisions, and reference-data evaluation.
let reviewDraft = null;
let reviewStartsNewAudit = false;
let savedAudit = null;
let selectedHistoryAudit = null;
let evaluationExamples = [];
const bloomLevels = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create'];
const byId = id => document.getElementById(id);
const lines = text => text.split('\n').map(s => s.trim()).filter(Boolean);

async function apiJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    const detail = data.message || data.detail || `Request failed (${response.status})`;
    throw new Error(Array.isArray(detail) ? detail.map(e => `${e.loc?.slice(1).join('.')}: ${e.msg}`).join('\n') : detail);
  }
  return data;
}
const jsonRequest = (method, value) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) });

function resetSavedAudit() {
  savedAudit = null;
  byId('history-title').value = '';
  byId('history-note').value = '';
  renderWorkspaceStatus();
}

function renderWorkspaceStatus() {
  byId('workspace-status').textContent = savedAudit
    ? `Editing saved audit ${savedAudit.audit_id.slice(0, 8)} · based on revision ${savedAudit.revision}. Save to create the next revision.`
    : 'Unsaved audit. Save a revision to reopen it later.';
  if (currentAuditReport) {
    const summary = currentAuditReport.paper_summary;
    byId('choice-summary').textContent = `${summary.choice_basis || 'All questions compulsory.'} Printed marks: ${summary.printed_marks ?? summary.total_marks}. Valid attempt marks: ${summary.minimum_attempt_marks ?? summary.total_marks}–${summary.maximum_attempt_marks ?? summary.total_marks}. Guaranteed unit coverage: ${summary.guaranteed_units ?? summary.covered_units}/${currentAuditReport.syllabus_summary.total_units}.`;
    if (!byId('history-title').value) byId('history-title').value = summary.paper_title;
  }
}

function editorInput(name, label, value = '', type = 'text') {
  return `<label>${escapeHtml(label)}<input data-field="${name}" type="${type}" value="${escapeHtml(value)}" ${type === 'number' ? 'step="any"' : ''}></label>`;
}
function editorText(name, label, value = '') {
  return `<label>${escapeHtml(label)}<textarea data-field="${name}" rows="3">${escapeHtml(value)}</textarea></label>`;
}
function appendRow(containerId, content) {
  const row = document.createElement('div');
  row.className = 'editor-row';
  row.innerHTML = '<button type="button" class="btn btn-secondary btn-sm remove-row">Remove</button>' + content;
  byId(containerId).append(row);
}
function field(row, name) { return row.querySelector(`[data-field="${name}"]`).value; }
function rows(id) { return [...byId(id).querySelectorAll('.editor-row')]; }

function addUnit(unit = {}) {
  appendRow('review-units', `<div class="editor-grid">${editorInput('number', 'Unit number', unit.unit_number || rows('review-units').length + 1, 'number')}${editorInput('title', 'Unit title', unit.title)}${editorInput('weight', 'Expected marks (%)', unit.weight ?? 0, 'number')}</div>${editorText('topics', 'Topics (one per line)', (unit.topics || []).join('\n'))}${editorText('outcomes', 'Learning outcomes (one per line)', (unit.learning_outcomes || []).join('\n'))}`);
}
function addQuestion(q = {}) {
  appendRow('review-questions', `<div class="editor-grid">${editorInput('id', 'Question ID', q.question_id || `Q${rows('review-questions').length + 1}`)}${editorInput('section', 'Section', q.section || 'General Section')}${editorInput('marks', 'Marks', q.marks ?? 10, 'number')}</div>${editorText('text', 'Question text', q.question_text)}`);
}
function addChoice(group = {}) {
  appendRow('review-choices', `<div class="editor-grid">${editorInput('id', 'Group ID', group.group_id || `CHOICE${rows('review-choices').length + 1}`)}${editorInput('ids', 'Question IDs (comma-separated)', (group.question_ids || []).join(', '))}${editorInput('choose', 'How many must be attempted?', group.choose || 1, 'number')}</div>`);
}
function addPyq(q = {}) {
  appendRow('review-pyqs', `<div class="editor-grid">${editorInput('id', 'Past question ID', q.question_id || `PYQ${rows('review-pyqs').length + 1}`)}${editorInput('year', 'Year / paper', q.paper_year || '')}${editorInput('marks', 'Marks', q.marks ?? 10, 'number')}</div>${editorText('text', 'Past question text', q.question_text)}`);
}

function openReviewDraft(draft, startsNewAudit = false) {
  reviewDraft = structuredClone(draft);
  reviewStartsNewAudit = startsNewAudit;
  byId('review-course-name').value = draft.syllabus.course_name;
  byId('review-course-code').value = draft.syllabus.course_code;
  byId('review-paper-title').value = draft.paper.paper_title;
  byId('review-warnings').innerHTML = (draft.warnings || []).map(w => `<li>${escapeHtml(w)}</li>`).join('');
  byId('review-source').textContent = Object.entries(draft.source_texts || {}).map(([key, value]) => `${key.toUpperCase()}\n${value}`).join('\n\n');
  ['review-units', 'review-questions', 'review-choices', 'review-pyqs'].forEach(id => byId(id).replaceChildren());
  draft.syllabus.units.forEach(unit => addUnit({ ...unit, weight: draft.rules.unit_weights[unit.unit_number] ?? unit.recommended_weightage_percent ?? 100 / draft.syllabus.units.length }));
  draft.paper.questions.forEach(addQuestion);
  (draft.paper.choice_groups || []).forEach(addChoice);
  draft.pyqs.forEach(addPyq);
  byId('review-component-weights').innerHTML = Object.entries(draft.rules.component_weights).map(([key, value]) => editorInput(key, key, value, 'number')).join('');
  byId('review-blooms-targets').innerHTML = Object.entries(draft.rules.blooms_targets).map(([key, value]) => editorInput(key, key, value, 'number')).join('');
  byId('review-repeat-medium').value = draft.rules.repeat_medium;
  byId('review-repeat-high').value = draft.rules.repeat_high;
  byId('review-error').textContent = '';
  byId('review-modal').classList.remove('hidden');
}

function readReviewDraft() {
  const draft = structuredClone(reviewDraft);
  draft.syllabus.course_name = byId('review-course-name').value.trim();
  draft.syllabus.course_code = byId('review-course-code').value.trim();
  draft.syllabus.units = rows('review-units').map(row => ({
    unit_number: Number(field(row, 'number')), title: field(row, 'title').trim(),
    topics: lines(field(row, 'topics')), learning_outcomes: lines(field(row, 'outcomes')),
    recommended_weightage_percent: Number(field(row, 'weight'))
  }));
  draft.rules.unit_weights = Object.fromEntries(draft.syllabus.units.map(u => [u.unit_number, u.recommended_weightage_percent]));
  draft.paper.paper_title = byId('review-paper-title').value.trim();
  draft.paper.course_code = draft.syllabus.course_code;
  draft.paper.questions = rows('review-questions').map(row => ({
    question_id: field(row, 'id').trim(), section: field(row, 'section').trim(),
    marks: Number(field(row, 'marks')), question_text: field(row, 'text').trim()
  }));
  draft.paper.total_marks = draft.paper.questions.reduce((sum, q) => sum + q.marks, 0);
  draft.paper.choice_groups = rows('review-choices').map(row => ({
    group_id: field(row, 'id').trim(), question_ids: field(row, 'ids').split(',').map(s => s.trim()).filter(Boolean), choose: Number(field(row, 'choose'))
  }));
  draft.pyqs = rows('review-pyqs').map(row => ({ question_id: field(row, 'id').trim(), paper_year: field(row, 'year'), marks: Number(field(row, 'marks')), question_text: field(row, 'text').trim() }));
  for (const [id, key] of [['review-component-weights', 'component_weights'], ['review-blooms-targets', 'blooms_targets']]) {
    draft.rules[key] = Object.fromEntries([...byId(id).querySelectorAll('input')].map(input => [input.dataset.field, Number(input.value)]));
  }
  draft.rules.repeat_medium = Number(byId('review-repeat-medium').value);
  draft.rules.repeat_high = Number(byId('review-repeat-high').value);
  return draft;
}

function activateReport(report) {
  currentAuditReport = report;
  currentSyllabus = report.syllabus;
  currentPyqs = report.pyqs || [];
  changedQuestionIds.clear();
  renderDashboard(report);
}
async function runReviewedAudit() {
  byId('review-error').textContent = '';
  byId('btn-run-reviewed').disabled = true;
  try {
    const draft = readReviewDraft();
    const report = await apiJson('/api/audit-reviewed', jsonRequest('POST', draft));
    if (reviewStartsNewAudit) resetSavedAudit();
    activateReport(report);
    byId('review-modal').classList.add('hidden');
  } catch (error) { byId('review-error').textContent = error.message; }
  finally { byId('btn-run-reviewed').disabled = false; }
}

async function saveAudit(asNew = false) {
  if (!currentAuditReport) return;
  byId('btn-save-revision').disabled = byId('btn-save-copy').disabled = true;
  try {
    if (!await recalculateFromTable()) return;
    const saved = await apiJson('/api/history', jsonRequest('POST', {
      report: currentAuditReport, audit_id: asNew ? null : savedAudit?.audit_id,
      expected_revision: asNew ? 0 : savedAudit?.revision || 0,
      title: byId('history-title').value.trim() || currentAuditReport.paper_summary.paper_title,
      note: byId('history-note').value
    }));
    savedAudit = saved;
    byId('history-note').value = '';
    renderWorkspaceStatus();
  } catch (error) { byId('workspace-status').textContent = `Could not save: ${error.message}`; }
  finally { byId('btn-save-revision').disabled = byId('btn-save-copy').disabled = false; }
}

async function openHistory() {
  byId('history-modal').classList.remove('hidden');
  byId('history-error').textContent = '';
  try {
    const audits = await apiJson('/api/history');
    byId('history-audits').innerHTML = audits.length ? audits.map(a => `<div class="history-entry"><strong>${escapeHtml(a.title)}</strong><span>Revision ${a.revision} · ${escapeHtml(new Date(a.created_at).toLocaleString())}</span><button class="btn btn-secondary" data-history-audit="${escapeHtml(a.audit_id)}">View revisions</button></div>`).join('') : '<p>No audits saved yet.</p>';
  } catch (error) { byId('history-error').textContent = error.message; }
}
async function viewRevisions(auditId) {
  selectedHistoryAudit = auditId;
  byId('history-error').textContent = '';
  byId('history-comparison').replaceChildren();
  try {
    const revisions = await apiJson(`/api/history/${encodeURIComponent(auditId)}/revisions`);
    byId('history-revisions').innerHTML = revisions.map(r => `<div class="history-entry"><strong>${escapeHtml(r.title)} · revision ${r.revision}</strong><span>${escapeHtml(r.note)} · ${escapeHtml(new Date(r.created_at).toLocaleString())}</span><button class="btn btn-secondary" data-open-revision="${r.revision}">Open revision</button></div>`).join('');
    byId('compare-after').value = revisions[0]?.revision || 1;
    byId('compare-before').value = revisions[1]?.revision || 1;
  } catch (error) { byId('history-error').textContent = error.message; }
}
async function openRevision(revision) {
  try {
    const saved = await apiJson(`/api/history/${encodeURIComponent(selectedHistoryAudit)}/revisions/${revision}`);
    savedAudit = { audit_id: saved.audit_id, revision: saved.revision };
    byId('history-title').value = saved.title;
    activateReport(saved.report);
    byId('history-modal').classList.add('hidden');
  } catch (error) { byId('history-error').textContent = error.message; }
}
async function compareRevisions() {
  if (!selectedHistoryAudit) { byId('history-error').textContent = 'Choose an audit first.'; return; }
  try {
    const comparison = await apiJson(`/api/history/${encodeURIComponent(selectedHistoryAudit)}/compare?before=${Number(byId('compare-before').value)}&after=${Number(byId('compare-after').value)}`);
    const changes = comparison.questions.map(q => `<tr><td>${escapeHtml(q.question_id)}</td><td>${escapeHtml(q.kind)}</td><td>${q.fields ? Object.entries(q.fields).map(([key, value]) => `${escapeHtml(key)}: ${escapeHtml(value.before)} → ${escapeHtml(value.after)}`).join('<br>') : escapeHtml((q.after || q.before).question_text)}</td></tr>`).join('');
    byId('history-comparison').innerHTML = `<h3>Revision ${comparison.before} → ${comparison.after}</h3><p>Score change: ${comparison.score_delta > 0 ? '+' : ''}${comparison.score_delta}. Rules changed: ${comparison.rules_changed ? 'yes' : 'no'}. Choices changed: ${comparison.choices_changed ? 'yes' : 'no'}. Syllabus changed: ${comparison.syllabus_changed ? 'yes' : 'no'}.</p><p>Component changes: ${escapeHtml(Object.entries(comparison.component_deltas).map(([key, delta]) => `${key.replaceAll('_', ' ')}: ${delta}`).join('; '))}</p><table class="comparison-table"><thead><tr><th>Question</th><th>Change</th><th>Details</th></tr></thead><tbody>${changes || '<tr><td colspan="3">No question changes.</td></tr>'}</tbody></table><p>Resolved: ${escapeHtml(comparison.resolved_findings.join('; ') || 'None')}</p><p>New: ${escapeHtml(comparison.new_findings.join('; ') || 'None')}</p><p>Updated findings: ${escapeHtml(comparison.changed_findings.join('; ') || 'None')}</p>`;
  } catch (error) { byId('history-error').textContent = error.message; }
}

function addReferenceLabel(label = {}) {
  appendRow('evaluation-labels', `<div class="editor-grid">${editorInput('id', 'Question ID', label.question_id || '')}${editorInput('unit', 'Expected unit (blank if outside syllabus)', label.expected_unit ?? '', 'number')}<label>Expected Bloom level<select data-field="blooms">${bloomLevels.map(level => `<option ${label.expected_blooms === level ? 'selected' : ''}>${level}</option>`).join('')}</select></label><label>Outside syllabus?<select data-field="oos"><option value="false">No</option><option value="true" ${label.expected_out_of_syllabus ? 'selected' : ''}>Yes</option></select></label></div>`);
}
function editExample(example) {
  byId('eval-id').value = example.example_id;
  byId('eval-reviewer').value = example.reviewer || '';
  byId('eval-count').value = example.expected_question_count;
  byId('eval-marks').value = example.expected_printed_marks;
  byId('eval-syllabus').value = example.syllabus_text;
  byId('eval-paper').value = example.paper_text;
  byId('evaluation-labels').replaceChildren();
  example.labels.forEach(addReferenceLabel);
}
async function openEvaluation() {
  byId('evaluation-modal').classList.remove('hidden');
  byId('evaluation-error').textContent = '';
  try {
    evaluationExamples = await apiJson('/api/evaluation/examples');
    byId('evaluation-example').innerHTML = evaluationExamples.map((example, index) => `<option value="${index}">${escapeHtml(example.example_id)} · ${example.reviewed_at ? 'reviewed' : 'draft'}</option>`).join('');
    if (evaluationExamples.length) editExample(evaluationExamples[0]);
  } catch (error) { byId('evaluation-error').textContent = error.message; }
}
async function saveExample() {
  const example = {
    example_id: byId('eval-id').value.trim(), reviewer: byId('eval-reviewer').value.trim(),
    syllabus_text: byId('eval-syllabus').value, paper_text: byId('eval-paper').value,
    expected_question_count: Number(byId('eval-count').value), expected_printed_marks: Number(byId('eval-marks').value),
    labels: rows('evaluation-labels').map(row => ({ question_id: field(row, 'id').trim(), expected_unit: field(row, 'unit') === '' ? null : Number(field(row, 'unit')), expected_blooms: field(row, 'blooms'), expected_out_of_syllabus: field(row, 'oos') === 'true' }))
  };
  try {
    await apiJson(`/api/evaluation/examples/${encodeURIComponent(example.example_id)}`, jsonRequest('PUT', example));
    await openEvaluation();
    byId('evaluation-error').textContent = `Saved ${example.example_id} as ${example.reviewer ? 'reviewed' : 'draft'}.`;
  } catch (error) { byId('evaluation-error').textContent = error.message; }
}
async function runEvaluation(includeDrafts = false) {
  try {
    const result = await apiJson(`/api/evaluation/run?include_drafts=${includeDrafts}`);
    const metrics = ['question_count_accuracy', 'printed_marks_accuracy', 'unit_accuracy', 'blooms_accuracy', 'out_of_syllabus_precision', 'out_of_syllabus_recall'];
    byId('evaluation-results').innerHTML = `<h3>${escapeHtml(result.mode)}</h3><p>${result.examples_evaluated} examples evaluated, ${result.examples_skipped} skipped. ${includeDrafts ? 'Draft checks do not establish faculty-validated accuracy.' : 'Only explicitly attributed reviews are included.'}</p><table class="comparison-table"><tbody>${metrics.map(key => `<tr><th>${escapeHtml(key.replaceAll('_', ' '))}</th><td>${result[key] === null ? 'No eligible data' : `${(result[key] * 100).toFixed(1)}%`}</td></tr>`).join('')}</tbody></table><details><summary>Inspect reference vs actual labels</summary><pre>${escapeHtml(JSON.stringify(result.details, null, 2))}</pre></details>`;
  } catch (error) { byId('evaluation-error').textContent = error.message; }
}
function exportExamples() {
  const url = URL.createObjectURL(new Blob([JSON.stringify(evaluationExamples, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url; link.download = 'examlens-evaluation.json'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

document.addEventListener('DOMContentLoaded', () => {
  // Keep dialogs outside the main content's stacking context so the sticky
  // navigation cannot cover their headings or close buttons.
  document.querySelectorAll('.modal-backdrop, .loading-overlay').forEach(dialog => document.body.append(dialog));
  document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => byId(button.dataset.close).classList.add('hidden')));
  document.addEventListener('click', event => {
    const remove = event.target.closest('.remove-row');
    if (remove) remove.closest('.editor-row').remove();
    const audit = event.target.closest('[data-history-audit]');
    if (audit) viewRevisions(audit.dataset.historyAudit);
    const revision = event.target.closest('[data-open-revision]');
    if (revision) openRevision(Number(revision.dataset.openRevision));
  });
  byId('btn-edit-documents').addEventListener('click', () => {
    if (!currentAuditReport) return;
    openReviewDraft({ syllabus: currentSyllabus, pyqs: currentPyqs, rules: currentAuditReport.rules,
      paper: { paper_title: currentAuditReport.paper_summary.paper_title, course_code: currentSyllabus.course_code,
        total_marks: currentAuditReport.paper_summary.printed_marks, questions: currentAuditReport.mapped_questions,
        choice_groups: currentAuditReport.choice_groups || [] }, warnings: [], source_texts: {} });
  });
  byId('btn-add-unit').addEventListener('click', () => addUnit());
  byId('btn-add-question').addEventListener('click', () => addQuestion());
  byId('btn-add-choice').addEventListener('click', () => addChoice());
  byId('btn-add-pyq').addEventListener('click', () => addPyq());
  byId('btn-run-reviewed').addEventListener('click', runReviewedAudit);
  byId('btn-save-revision').addEventListener('click', () => saveAudit());
  byId('btn-save-copy').addEventListener('click', () => saveAudit(true));
  byId('btn-open-history').addEventListener('click', openHistory);
  byId('btn-compare-revisions').addEventListener('click', compareRevisions);
  byId('btn-open-evaluation').addEventListener('click', openEvaluation);
  byId('evaluation-example').addEventListener('change', event => editExample(evaluationExamples[Number(event.target.value)]));
  byId('btn-run-evaluation').addEventListener('click', () => runEvaluation());
  byId('btn-smoke-evaluation').addEventListener('click', () => runEvaluation(true));
  byId('btn-add-label').addEventListener('click', () => addReferenceLabel());
  byId('btn-save-example').addEventListener('click', saveExample);
  byId('btn-export-examples').addEventListener('click', exportExamples);
  byId('btn-new-example').addEventListener('click', () => editExample({ example_id: '', syllabus_text: '', paper_text: '', expected_question_count: 1, expected_printed_marks: 10, labels: [] }));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') document.querySelectorAll('.modal-backdrop:not(.hidden)').forEach(dialog => dialog.classList.add('hidden'));
  });
});
