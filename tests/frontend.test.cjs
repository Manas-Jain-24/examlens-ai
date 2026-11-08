const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function dashboard() {
  const elements = {};
  const document = {
    addEventListener() {},
    querySelectorAll: () => [{ querySelector: sel => ({ value: sel === '.select-unit' ? '1' : 'Remember' }) }],
    getElementById: id => elements[id] ||= { value: '', classList: { add() {}, remove() {} } },
  };
  const ctx = vm.createContext({ document, console });
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
