const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function dashboard() {
  const elements = {};
  const document = {
    addEventListener() {},
    querySelectorAll: () => [{ querySelector: sel => ['.select-unit', '.select-blooms'].includes(sel) ? ({ value: sel === '.select-unit' ? '1' : 'Remember' }) : null }],
    getElementById: id => elements[id] ||= { value: '', classList: { add() {}, remove() {} } },
  };
  const ctx = vm.createContext({ document, console, structuredClone });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../frontend/app.js'), 'utf8'), ctx);
  vm.runInContext(`
    currentSyllabus = { units: [] };
    currentAuditReport = { paper_summary: { paper_title: 'Draft' }, mapped_questions: [
      { question_id: 'Q2', question_text: 'Define arrays', marks: 5 }
    ] };
    showLoading = () => {};
    hideLoading = () => {};
    renderDashboard = () => {};
    var lastPayload = null;
    fetch = async (url, options) => {
      lastPayload = JSON.parse(options.body);
      return { ok: true, json: async () => ({
        ...currentAuditReport, mapped_questions: lastPayload.questions
      }) };
    };
  `, ctx);
  return { ctx, elements };
}

test('generated questions survive collecting table overrides with unique IDs', async () => {
  const { ctx } = dashboard();
  await vm.runInContext(`
    activeGenerateUnit = { unit_number: 1, learning_outcomes: [] };
    generatedCandidates = [{ question_text: 'Analyze arrays', marks: 10, blooms_level: 'Analyze' }];
    addGeneratedQuestionToPaper(0);
  `, ctx);
  assert.equal(vm.runInContext('currentAuditReport.mapped_questions.length', ctx), 2);
  assert.equal(vm.runInContext('currentAuditReport.mapped_questions[1].question_id', ctx), 'Q3');
  assert.equal(vm.runInContext('lastPayload.questions.length', ctx), 2);
  assert.equal(vm.runInContext('lastPayload.changed_question_ids.includes("Q3")', ctx), true);
});

test('rewrites preserve target level until server re-audits and mark changed text', async () => {
  const { ctx, elements } = dashboard();
  elements['rewrite-result-text'] = { value: 'Analyze arrays' };
  elements['select-target-blooms'] = { value: 'Analyze' };
  await vm.runInContext('activeRewriteIndex = 0; applyAIRewrite();', ctx);
  assert.equal(vm.runInContext('currentAuditReport.mapped_questions[0].blooms_level', ctx), 'Analyze');
  assert.equal(vm.runInContext('lastPayload.changed_question_ids.includes("Q2")', ctx), true);
});

test('uploaded question text and tooltip payloads are escaped in rendered table', () => {
  const { ctx, elements } = dashboard();
  vm.runInContext(`renderQuestionsTable([{
    question_id: 'Q1', question_text: '<img src=x onerror=alert(1)>',
    is_out_of_syllabus: true, out_of_syllabus_reason: '\" onmouseover=\"alert(1)',
    marks: 5
  }], []);`, ctx);
  const html = elements['questions-table-body'].innerHTML;
  assert.ok(html.includes('&lt;img'));
  assert.ok(html.includes('&quot; onmouseover='));
  assert.ok(!html.includes('<img'));
  assert.ok(!html.includes('title="" onmouseover='));
});

test('recalculation submits course rules and optional choice groups', async () => {
  const { ctx } = dashboard();
  await vm.runInContext(`
    currentAuditReport.rules = { repeat_medium: 0.6, repeat_high: 0.9 };
    currentAuditReport.choice_groups = [{ group_id: 'ANY1', question_ids: ['Q2','Q3'], choose: 1 }];
    recalculateFromTable();
  `, ctx);
  assert.equal(vm.runInContext('lastPayload.rules.repeat_high', ctx), 0.9);
  assert.equal(vm.runInContext('lastPayload.choice_groups[0].choose', ctx), 1);
});

test('saving a revision stops if recalculation fails', async () => {
  const { ctx } = dashboard();
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../frontend/workspace.js'), 'utf8'), ctx);
  await vm.runInContext(`
    var saveCalled = false;
    recalculateFromTable = async () => false;
    apiJson = async () => { saveCalled = true; };
    saveAudit();
  `, ctx);
  assert.equal(vm.runInContext('saveCalled', ctx), false);
});

test('API validation errors identify correction fields', async () => {
  const { ctx } = dashboard();
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../frontend/workspace.js'), 'utf8'), ctx);
  const message = await vm.runInContext(`
    fetch = async () => ({ ok: false, json: async () => ({ detail: [
      { loc: ['body','paper','choice_groups'], msg: 'Groups cannot overlap' }
    ] }) });
    apiJson('/api/audit-reviewed').catch(error => error.message);
  `, ctx);
  assert.equal(message, 'paper.choice_groups: Groups cannot overlap');
});

test('saving uses current report, revision base, and revision note', async () => {
  const { ctx, elements } = dashboard();
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../frontend/workspace.js'), 'utf8'), ctx);
  elements['history-title'] = { value: 'Course final' };
  elements['history-note'] = { value: 'Corrected OR choices' };
  await vm.runInContext(`
    recalculateFromTable = async () => true;
    renderWorkspaceStatus = () => {};
    savedAudit = { audit_id: 'example', revision: 2 };
    apiJson = async (url, options) => {
      lastPayload = JSON.parse(options.body);
      return {audit_id:'example',revision:3};
    };
    saveAudit();
  `, ctx);
  assert.equal(vm.runInContext('lastPayload.expected_revision', ctx), 2);
  assert.equal(vm.runInContext('lastPayload.note', ctx), 'Corrected OR choices');
  assert.equal(vm.runInContext('savedAudit.revision', ctx), 3);
});
