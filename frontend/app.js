// ExamLens AI — Frontend Logic & Interactive Engine

let currentAuditReport = null;
let currentSyllabus = null;
let currentPyqs = [];
const changedQuestionIds = new Set();
let bloomsChartInstance = null;
let marksChartInstance = null;

// Every value originating from a document upload or an AI response must be
// escaped before it is interpolated into an HTML template.
function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  loadDemoAudit();
});

function setupEventListeners() {
  // Demo button
  document.getElementById('btn-load-demo').addEventListener('click', () => {
    loadDemoAudit();
  });

  // Modal open / close
  const modal = document.getElementById('upload-modal');
  document.getElementById('btn-open-upload').addEventListener('click', () => {
    modal.classList.remove('hidden');
  });
  document.getElementById('btn-close-modal').addEventListener('click', () => {
    modal.classList.add('hidden');
  });
  document.getElementById('btn-cancel-upload').addEventListener('click', () => {
    modal.classList.add('hidden');
  });

  // File input labels update
  setupFileInput('file-syllabus', 'name-syllabus');
  setupFileInput('file-paper', 'name-paper');
  setupFileInput('file-pyq', 'name-pyq');

  // Audit Form Submission
  document.getElementById('audit-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    await handleFormAudit();
  });

  // Human-in-the-Loop Recalculate Button
  document.getElementById('btn-recalculate').addEventListener('click', () => {
    recalculateFromTable();
  });

  // Export PDF Button
  document.getElementById('btn-export-pdf').addEventListener('click', () => {
    exportPdfReport();
  });

  // Findings Filter Tabs
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      const filter = e.target.getAttribute('data-filter');
      filterFindings(filter);
    });
  });
}

function setupFileInput(inputId, nameId) {
  const input = document.getElementById(inputId);
  const nameSpan = document.getElementById(nameId);
  input.addEventListener('change', () => {
    if (input.files.length > 0) {
      nameSpan.textContent = input.files[0].name;
      nameSpan.style.color = '#818cf8';
    } else {
      nameSpan.textContent = 'No file selected';
      nameSpan.style.color = '';
    }
  });
}

// Show / Hide Loading Overlay
function showLoading(stepText = 'Auditing Assessment Quality...') {
  const overlay = document.getElementById('loading-state');
  document.getElementById('loading-step').textContent = stepText;
  overlay.classList.remove('hidden');
}

function hideLoading() {
  document.getElementById('loading-state').classList.add('hidden');
}

// Fetch & Render Demo Audit
async function loadDemoAudit() {
  showLoading('Loading CS201 Data Structures and Algorithms pre-built audit...');
  try {
    const res = await fetch('/api/demo');
    if (!res.ok) throw new Error(`Server returned ${res.status}`);
    const report = await res.json();
    currentAuditReport = report;
    
    currentSyllabus = report.syllabus;
    currentPyqs = report.pyqs || [];
    changedQuestionIds.clear();

    renderDashboard(report);
  } catch (err) {
    alert('Error loading demo audit: ' + err.message);
  } finally {
    hideLoading();
  }
}

// Form Upload Handler
async function handleFormAudit() {
  const fileSyl = document.getElementById('file-syllabus').files[0];
  const textSyl = document.getElementById('text-syllabus').value.trim();
  const filePaper = document.getElementById('file-paper').files[0];
  const textPaper = document.getElementById('text-paper').value.trim();
  const filePyq = document.getElementById('file-pyq').files[0];
  const textPyq = document.getElementById('text-pyq').value.trim();

  if (!fileSyl && !textSyl) {
    alert('Please select a syllabus file or paste syllabus text.');
    return;
  }
  if (!filePaper && !textPaper) {
    alert('Please select a question paper file or paste question paper text.');
    return;
  }

  const formData = new FormData();
  if (fileSyl) formData.append('syllabus_file', fileSyl);
  if (textSyl) formData.append('syllabus_text', textSyl);
  if (filePaper) formData.append('paper_file', filePaper);
  if (textPaper) formData.append('paper_text', textPaper);
  if (filePyq) formData.append('pyq_file', filePyq);
  if (textPyq) formData.append('pyq_text', textPyq);

  document.getElementById('upload-modal').classList.add('hidden');
  showLoading('Extracting syllabus structure, mapping questions, and auditing quality metrics...');

  try {
    const res = await fetch('/api/audit', {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.message || errData.detail || `Server error ${res.status}`);
    }
    const report = await res.json();
    currentAuditReport = report;
    
    currentSyllabus = report.syllabus;
    currentPyqs = report.pyqs || [];
    changedQuestionIds.clear();

    renderDashboard(report);
  } catch (err) {
    alert('Audit failed: ' + err.message);
  } finally {
    hideLoading();
  }
}

// Recalculate with Faculty Overrides
function collectTableOverrides() {
  const rows = document.querySelectorAll('#questions-table-body tr');
  currentAuditReport.mapped_questions = currentAuditReport.mapped_questions.map((q, idx) => {
    const row = rows[idx];
    if (!row) return q;
    return {
      ...q,
      mapped_unit: parseInt(row.querySelector('.select-unit').value, 10),
      blooms_level: row.querySelector('.select-blooms').value
    };
  });
}

async function recalculateFromTable(readTable = true) {
  if (!currentAuditReport || !currentSyllabus) return;
  if (readTable) collectTableOverrides();

  showLoading('Recalculating Exam Quality Score & Unit Coverage with faculty overrides...');

  try {
    const payload = {
      syllabus: currentSyllabus,
      questions: currentAuditReport.mapped_questions,
      changed_question_ids: [...changedQuestionIds],
      pyqs: currentPyqs,
      paper_title: currentAuditReport.paper_summary.paper_title
    };

    const res = await fetch('/api/recalculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error('Recalculation failed');
    const newReport = await res.json();
    currentAuditReport = newReport;
    changedQuestionIds.clear();
    renderDashboard(newReport);
  } catch (err) {
    alert('Error recalculating score: ' + err.message);
  } finally {
    hideLoading();
  }
}

// Render Entire Dashboard
function renderDashboard(report) {
  // Show PDF Export and AI Summary buttons
  document.getElementById('btn-export-pdf').style.display = 'inline-flex';
  const aiSummaryBtn = document.getElementById('btn-ai-summary');
  if (aiSummaryBtn) aiSummaryBtn.style.display = 'inline-flex';


  // 1. Header Information
  document.getElementById('disp-course-code').textContent = report.syllabus_summary.course_code || 'COURSE';
  document.getElementById('disp-course-name').textContent = report.syllabus_summary.course_name || 'Course Examination';
  document.getElementById('disp-paper-title').innerHTML = `<i class="fa-regular fa-file-lines"></i> ${escapeHtml(report.paper_summary.paper_title || 'Draft Examination Paper')}`;
  document.getElementById('disp-total-marks').textContent = `${report.paper_summary.total_marks || 100} M`;
  document.getElementById('disp-total-questions').textContent = `${report.paper_summary.total_questions || 0} Items`;
  document.getElementById('disp-coverage-ratio').textContent = `${report.paper_summary.covered_units || 0} / ${report.syllabus_summary.total_units || 0} Units`;

  // 2. Score Dial & Grade
  const scoreVal = report.overall_quality_score;
  document.getElementById('disp-overall-score').textContent = scoreVal.toFixed(1);
  document.getElementById('disp-grade').textContent = report.grade;
  document.getElementById('disp-verdict-summary').textContent = report.verdict_summary;

  const circle = document.getElementById('score-circle-progress');
  circle.setAttribute('stroke-dasharray', `${scoreVal}, 100`);
  
  if (scoreVal >= 80) {
    circle.style.stroke = '#10b981';
    document.getElementById('disp-grade').className = 'grade-tag badge-success';
  } else if (scoreVal >= 70) {
    circle.style.stroke = '#f59e0b';
    document.getElementById('disp-grade').className = 'grade-tag badge-warning';
  } else {
    circle.style.stroke = '#ef4444';
    document.getElementById('disp-grade').className = 'grade-tag badge-danger';
  }

  // 3. Score Breakdown Progress Bars
  renderScoreBreakdown(report.score_breakdown);

  // 4. Render Charts
  renderBloomsRadarChart(report.blooms_distribution);
  renderMarksBarChart(report.unit_coverage);

  // 5. Unit Coverage Matrix Cards
  renderUnitCoverageMatrix(report.unit_coverage);

  // 6. Findings & Moderation Directives
  renderFindings(report.findings);

  // 7. Human-in-the-Loop Question Review Table
  renderQuestionsTable(report.mapped_questions, report.unit_coverage);
}

function renderScoreBreakdown(sb) {
  const container = document.getElementById('score-breakdown-container');
  const items = [
    { label: 'Syllabus Coverage', score: sb.syllabus_coverage_score, weight: '25%' },
    { label: 'Learning Outcomes Alignment', score: sb.learning_outcomes_score, weight: '20%' },
    { label: 'Marks Weightage Balance', score: sb.marks_distribution_score, weight: '20%' },
    { label: "Bloom's Cognitive Balance", score: sb.blooms_cognitive_score, weight: '15%' },
    { label: 'Out-of-Syllabus Cleanliness', score: sb.out_of_syllabus_score, weight: '10%' },
    { label: 'Repetition Risk Cleanliness', score: sb.repetition_risk_score, weight: '10%' }
  ];

  container.innerHTML = items.map(item => `
    <div class="breakdown-item">
      <div class="breakdown-labels">
        <span>${item.label} <small style="color: var(--text-dim);">(${item.weight})</small></span>
        <span>${item.score.toFixed(0)}%</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" style="width: ${Math.min(100, item.score)}%;"></div>
      </div>
    </div>
  `).join('');
}

function renderBloomsRadarChart(bloomsData) {
  const ctx = document.getElementById('bloomsRadarChart').getContext('2d');
  if (bloomsChartInstance) bloomsChartInstance.destroy();

  const labels = bloomsData.map(b => b.level);
  const dataValues = bloomsData.map(b => b.percentage);

  bloomsChartInstance = new Chart(ctx, {
    type: 'radar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Exam Marks %',
        data: dataValues,
        backgroundColor: 'rgba(99, 102, 241, 0.25)',
        borderColor: '#818cf8',
        borderWidth: 2,
        pointBackgroundColor: '#6366f1',
        pointBorderColor: '#fff',
        pointHoverRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          angleLines: { color: 'rgba(255, 255, 255, 0.08)' },
          grid: { color: 'rgba(255, 255, 255, 0.08)' },
          pointLabels: {
            color: '#cbd5e1',
            font: { family: 'Plus Jakarta Sans', size: 11, weight: '600' }
          },
          ticks: {
            backdropColor: 'transparent',
            color: '#64748b',
            font: { size: 9 },
            stepSize: 15
          },
          suggestedMin: 0,
          suggestedMax: 40
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.dataset.label}: ${ctx.raw}%`
          }
        }
      }
    }
  });
}

function renderMarksBarChart(unitCoverage) {
  const ctx = document.getElementById('marksBarChart').getContext('2d');
  if (marksChartInstance) marksChartInstance.destroy();

  const labels = unitCoverage.map(u => `Unit ${u.unit_number}`);
  const actualMarksPct = unitCoverage.map(u => u.marks_percentage);
  const expectedMarksPct = unitCoverage.map(u => u.expected_weightage_percent);

  marksChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Actual Marks %',
          data: actualMarksPct,
          backgroundColor: 'rgba(99, 102, 241, 0.75)',
          borderRadius: 6,
          barPercentage: 0.65
        },
        {
          label: 'Expected Weight %',
          data: expectedMarksPct,
          backgroundColor: 'rgba(255, 255, 255, 0.15)',
          borderRadius: 6,
          barPercentage: 0.65
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 10, weight: '600' } }
        },
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.06)' },
          ticks: {
            color: '#64748b',
            callback: (v) => v + '%',
            font: { size: 10 }
          },
          suggestedMax: 40
        }
      },
      plugins: {
        legend: {
          position: 'top',
          align: 'end',
          labels: {
            color: '#94a3b8',
            boxWidth: 12,
            font: { size: 10, family: 'Plus Jakarta Sans', weight: '500' }
          }
        }
      }
    }
  });
}

function renderUnitCoverageMatrix(unitStats) {
  const container = document.getElementById('unit-coverage-grid');
  container.innerHTML = unitStats.map(u => {
    let statusClass = 'status-well-covered';
    let badgeHtml = '<span class="badge badge-success"><i class="fa-solid fa-check"></i> Well Covered</span>';

    if (u.coverage_status === 'Not Assessed') {
      statusClass = 'status-not-assessed';
      badgeHtml = '<span class="badge badge-danger"><i class="fa-solid fa-triangle-exclamation"></i> Not Assessed</span>';
    } else if (u.coverage_status === 'Overrepresented') {
      statusClass = 'status-overrepresented';
      badgeHtml = '<span class="badge badge-warning"><i class="fa-solid fa-arrow-trend-up"></i> Overrepresented</span>';
    } else if (u.coverage_status === 'Underrepresented') {
      statusClass = 'status-underrepresented';
      badgeHtml = '<span class="badge badge-info"><i class="fa-solid fa-arrow-trend-down"></i> Underrepresented</span>';
    }

    const showAiGen = (u.coverage_status === 'Not Assessed' || u.coverage_status === 'Underrepresented');
    const aiGenBtn = showAiGen ? `
      <button class="btn btn-xs btn-outline-ai" onclick="openAIGapFiller(${u.unit_number})">
        <i class="fa-solid fa-wand-magic-sparkles"></i> AI Generate Question
      </button>
    ` : '';

    return `
      <div class="unit-card ${statusClass}">
        <div>
          <div class="unit-card-header">
            <span class="unit-tag">UNIT ${u.unit_number}</span>
            ${badgeHtml}
          </div>
          <h4>${escapeHtml(u.unit_title)}</h4>
        </div>
        <div class="unit-card-stats">
          <span>Questions: <strong>${u.questions_count}</strong></span>
          <span>Marks: <strong>${u.total_marks}M (${u.marks_percentage}%)</strong></span>
          <span>Exp: <strong>${u.expected_weightage_percent}%</strong></span>
        </div>
        ${aiGenBtn}
      </div>
    `;

  }).join('');
}

function renderFindings(findings) {
  const countBadge = document.getElementById('disp-findings-count');
  countBadge.textContent = `${findings.length} Alerts`;
  filterFindings('all');
}

function filterFindings(categoryFilter) {
  const container = document.getElementById('findings-list-container');
  if (!currentAuditReport || !currentAuditReport.findings) return;

  const findings = currentAuditReport.findings;
  const filtered = categoryFilter === 'all' 
    ? findings 
    : findings.filter(f => f.category.toLowerCase() === categoryFilter.toLowerCase());

  if (filtered.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 2rem; color: var(--text-dim); font-size: 0.9rem;">
        <i class="fa-solid fa-circle-check" style="color: var(--success); font-size: 1.5rem; margin-bottom: 8px; display: block;"></i>
        No warnings found in this category. Assessment meets benchmarks.
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(f => {
    const sevClass = f.severity === 'High' ? 'sev-high' : (f.severity === 'Medium' ? 'sev-medium' : 'sev-low');
    const badgeSevClass = f.severity === 'High' ? 'badge-danger' : (f.severity === 'Medium' ? 'badge-warning' : 'badge-info');

    return `
      <div class="finding-item ${sevClass}">
        <div class="finding-header">
          <div class="finding-title-group">
            <span class="badge ${badgeSevClass}">${escapeHtml(f.severity)}</span>
            <span class="finding-category-tag">${escapeHtml(f.category)}</span>
            <h4>${escapeHtml(f.title)}</h4>
          </div>
        </div>
        <p class="finding-msg">${escapeHtml(f.message)}</p>
        <div class="finding-action">
          <i class="fa-solid fa-bullseye" style="color: var(--primary-light); margin-right: 6px;"></i>
          <strong>Recommended Action:</strong> ${escapeHtml(f.recommended_action)}
        </div>
      </div>
    `;
  }).join('');
}

function renderQuestionsTable(questions, unitCoverage) {
  const tbody = document.getElementById('questions-table-body');
  const bloomsLevels = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create'];

  tbody.innerHTML = questions.map((q, idx) => {
    // Unit select options
    const unitOptions = unitCoverage.map(u => 
      `<option value="${u.unit_number}" ${q.mapped_unit === u.unit_number ? 'selected' : ''}>Unit ${u.unit_number}: ${escapeHtml(u.unit_title.substring(0, 24))}...</option>`
    ).join('');

    // Blooms select options
    const bloomsOptions = bloomsLevels.map(lvl => 
      `<option value="${lvl}" ${q.blooms_level === lvl ? 'selected' : ''}>${lvl}</option>`
    ).join('');

    // Confidence badge
    const confVal = q.mapping_confidence || 0.5;
    let confClass = 'conf-med';
    if (confVal >= 0.75) confClass = 'conf-high';
    else if (confVal < 0.45) confClass = 'conf-low';

    // Alerts
    let alertsHtml = '<span style="color: var(--text-dim); font-size: 0.75rem;">None</span>';
    if (q.is_out_of_syllabus) {
      alertsHtml = `<span class="badge badge-danger" title="${escapeHtml(q.out_of_syllabus_reason || 'Out of syllabus')}"><i class="fa-solid fa-triangle-exclamation"></i> Out-of-Syllabus</span>`;
    } else if (q.pyq_similarity && q.pyq_similarity >= 0.70) {
      const matchPct = Math.round(q.pyq_similarity * 100);
      alertsHtml = `<span class="badge badge-warning" title="${escapeHtml(q.pyq_matched_question || '')}"><i class="fa-solid fa-copy"></i> ${matchPct}% Repeat</span>`;
    }

    return `
      <tr data-index="${idx}">
        <td><span class="q-id-pill">${escapeHtml(q.question_id)}</span></td>
        <td><span style="font-size: 0.75rem; color: var(--text-dim);">${escapeHtml(q.section || 'Part A')}</span></td>
        <td>
          <div class="q-statement">${escapeHtml(q.question_text)}</div>
          <div class="q-subinfo">
            <span>Type: ${escapeHtml(q.question_type || 'Descriptive')}</span>
            ${q.command_verb ? ` • Verb: <em style="color: var(--primary-light);">${escapeHtml(q.command_verb)}</em>` : ''}
          </div>
        </td>
        <td><span class="marks-badge">${q.marks}M</span></td>
        <td>
          <select class="select-edit select-unit">
            ${unitOptions}
          </select>
        </td>
        <td>
          <select class="select-edit select-blooms">
            ${bloomsOptions}
          </select>
        </td>
        <td>
          <span class="conf-pill ${confClass}">${Math.round(confVal * 100)}%</span>
        </td>
        <td>${alertsHtml}</td>
        <td>
          <button class="btn btn-xs btn-ai-rewrite" onclick="openAIRewriter(${idx})">
            <i class="fa-solid fa-wand-magic-sparkles"></i> AI Rewrite
          </button>
        </td>
      </tr>
    `;

  }).join('');
}

// PDF Export Function
async function exportPdfReport() {
  if (!currentAuditReport) {
    alert('No audit report loaded to export.');
    return;
  }

  showLoading('Generating official institutional PDF audit report...');
  try {
    const res = await fetch('/api/export-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentAuditReport)
    });

    if (!res.ok) throw new Error('Failed to generate PDF');

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ExamLens_Audit_Report_${currentAuditReport.syllabus_summary.course_code || 'CS201'}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (err) {
    alert('PDF export failed: ' + err.message);
  } finally {
    hideLoading();
  }
}

// ============================================================================
// Phase 2: Gemini AI Integration Frontend Handlers
// ============================================================================

let activeRewriteIndex = null;
let activeGenerateUnit = null;
let generatedCandidates = [];

// --- 1. AI Question Rewriter ---
function openAIRewriter(idx) {
  if (!currentAuditReport || !currentAuditReport.mapped_questions) return;
  activeRewriteIndex = idx;
  const q = currentAuditReport.mapped_questions[idx];

  document.getElementById('rewrite-orig-text').textContent = q.question_text;
  document.getElementById('rewrite-orig-blooms').textContent = `Current: ${q.blooms_level || 'Understand'}`;

  const issueBadge = document.getElementById('rewrite-orig-issue');
  if (q.is_out_of_syllabus) {
    issueBadge.textContent = 'Issue: Out-of-Syllabus';
    issueBadge.className = 'badge badge-danger';
  } else if (q.pyq_similarity && q.pyq_similarity >= 0.70) {
    issueBadge.textContent = `Issue: ${Math.round(q.pyq_similarity * 100)}% Past Repeat`;
    issueBadge.className = 'badge badge-warning';
  } else if (q.blooms_level === 'Remember') {
    issueBadge.textContent = 'Issue: Rote Recall Bias';
    issueBadge.className = 'badge badge-warning';
  } else {
    issueBadge.textContent = 'Objective: Cognitive Elevation';
    issueBadge.className = 'badge badge-info';
  }

  // Preselect a higher target
  const targetSelect = document.getElementById('select-target-blooms');
  targetSelect.value = q.blooms_level === 'Remember' ? 'Apply' : (q.blooms_level === 'Apply' ? 'Analyze' : 'Evaluate');

  document.getElementById('ai-rewrite-output-container').classList.add('hidden');
  document.getElementById('ai-rewrite-modal').classList.remove('hidden');
}

async function runAIRewrite() {
  if (activeRewriteIndex === null) return;
  const q = currentAuditReport.mapped_questions[activeRewriteIndex];
  const targetBlooms = document.getElementById('select-target-blooms').value;

  const btn = document.getElementById('btn-run-ai-rewrite');
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating...';

  try {
    const payload = {
      question_text: q.question_text,
      current_blooms_level: q.blooms_level || 'Understand',
      target_blooms_level: targetBlooms,
      issue_reason: q.out_of_syllabus_reason || (q.is_out_of_syllabus ? 'Out of syllabus' : 'Elevate cognitive level'),
      syllabus_context: currentSyllabus ? currentSyllabus.course_name : '',
      marks: q.marks || 10.0
    };

    const res = await fetch('/api/ai/rewrite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error('AI Rewrite request failed');
    const data = await res.json();

    document.getElementById('rewrite-result-text').value = data.rewritten_question;
    document.getElementById('rewrite-rationale-text').textContent = data.pedagogical_rationale;
    document.getElementById('rewrite-engine-badge').textContent = data.is_ai_generated ? 'Gemini 3.8 Flash' : 'Smart Heuristic Engine';

    document.getElementById('ai-rewrite-output-container').classList.remove('hidden');
  } catch (err) {
    alert('AI Rewrite error: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-bolt"></i> Generate AI Rewrite';
  }
}

async function applyAIRewrite() {
  if (activeRewriteIndex === null) return;
  const newText = document.getElementById('rewrite-result-text').value.trim();
  const targetBlooms = document.getElementById('select-target-blooms').value;

  if (!newText) {
    alert('Please generate or enter a rewritten question.');
    return;
  }

  collectTableOverrides();
  // The server will audit the new text before assigning fresh annotations.
  const q = currentAuditReport.mapped_questions[activeRewriteIndex];
  q.question_text = newText;
  q.blooms_level = targetBlooms;
  changedQuestionIds.add(q.question_id);

  // Close modal
  document.getElementById('ai-rewrite-modal').classList.add('hidden');

  // Trigger recalculation with overrides
  await recalculateFromTable(false);
}

// --- 2. AI Unit Gap Filler ---
function openAIGapFiller(unitNumber) {
  if (!currentSyllabus || !currentSyllabus.units) return;
  const unit = currentSyllabus.units.find(u => u.unit_number === unitNumber);
  if (!unit) return;

  activeGenerateUnit = unit;
  document.getElementById('gen-unit-title').textContent = `Unit ${unit.unit_number}: ${unit.title}`;
  document.getElementById('gen-unit-topics').textContent = `Prescribed Topics: ${unit.topics.join(' • ')}`;
  document.getElementById('gen-candidates-container').classList.add('hidden');
  document.getElementById('gen-candidates-container').innerHTML = '';
  document.getElementById('ai-generate-modal').classList.remove('hidden');
}

async function runAIGenerateQuestions() {
  if (!activeGenerateUnit) return;
  const targetBlooms = document.getElementById('gen-target-blooms').value;
  const marks = parseFloat(document.getElementById('gen-target-marks').value);

  const btn = document.getElementById('btn-run-ai-generate');
  btn.disabled = true;
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating Questions...';

  try {
    const payload = {
      course_name: currentSyllabus.course_name,
      course_code: currentSyllabus.course_code,
      unit_number: activeGenerateUnit.unit_number,
      unit_title: activeGenerateUnit.title,
      unit_topics: activeGenerateUnit.topics,
      target_blooms_level: targetBlooms,
      marks: marks,
      difficulty: 'Medium'
    };

    const res = await fetch('/api/ai/generate-question', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error('Question generation failed');
    const data = await res.json();
    generatedCandidates = data.candidates || [];

    const container = document.getElementById('gen-candidates-container');
    container.innerHTML = generatedCandidates.map((c, i) => `
      <div class="candidate-card">
        <div class="candidate-header">
          <div>
            <span class="badge badge-info">${escapeHtml(c.blooms_level)}</span>
            <span class="marks-badge" style="margin-left: 6px;">${c.marks}M</span>
          </div>
          <button class="btn btn-xs btn-success" onclick="addGeneratedQuestionToPaper(${i})">
            <i class="fa-solid fa-plus"></i> Add to Exam Paper
          </button>
        </div>
        <div class="candidate-statement">${escapeHtml(c.question_text)}</div>
        ${c.sample_solution_outline ? `<div class="candidate-solution"><strong>Rubric:</strong> ${escapeHtml(c.sample_solution_outline)}</div>` : ''}
      </div>
    `).join('');

    container.classList.remove('hidden');
  } catch (err) {
    alert('AI Generation error: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Generate Questions';
  }
}

async function addGeneratedQuestionToPaper(candIndex) {
  if (!activeGenerateUnit || !generatedCandidates[candIndex]) return;
  const candidate = generatedCandidates[candIndex];

  collectTableOverrides();
  const usedIds = new Set(currentAuditReport.mapped_questions.map(q => q.question_id));
  let nextId = currentAuditReport.mapped_questions.length + 1;
  while (usedIds.has(`Q${nextId}`)) nextId++;
  const newQId = `Q${nextId}`;
  const newQuestion = {
    question_id: newQId,
    section: 'Part B',
    question_text: candidate.question_text,
    marks: candidate.marks,
    question_type: 'Descriptive',
    command_verb: candidate.command_verb,
    mapped_unit: activeGenerateUnit.unit_number,
    mapped_outcomes: activeGenerateUnit.learning_outcomes || [],
    blooms_level: candidate.blooms_level,
    mapping_confidence: 0.0,
    is_out_of_syllabus: false,
    out_of_syllabus_reason: null,
    pyq_similarity: 0.0,
    pyq_matched_question: null
  };

  currentAuditReport.mapped_questions.push(newQuestion);
  changedQuestionIds.add(newQId);
  document.getElementById('ai-generate-modal').classList.add('hidden');

  // Trigger recalculation to reflect the filled unit in charts and scores
  await recalculateFromTable(false);
}

// --- 3. AI Accreditation Executive Summary ---
async function openAIModerationSummary() {
  if (!currentAuditReport) return;
  const modal = document.getElementById('ai-summary-modal');
  modal.classList.remove('hidden');

  const narrativeElem = document.getElementById('summary-narrative');
  narrativeElem.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating accreditation intelligence note...';

  try {
    const res = await fetch('/api/ai/moderation-summary', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ report: currentAuditReport })
    });

    if (!res.ok) throw new Error('Failed to generate summary');
    const data = await res.json();

    document.getElementById('summary-readiness-badge').textContent = data.nba_abet_readiness;
    narrativeElem.textContent = data.accreditation_summary;

    const strengthsList = document.getElementById('summary-strengths-list');
    strengthsList.innerHTML = (data.key_strengths || []).map(s => `<li>${escapeHtml(s)}</li>`).join('');

    const actionsList = document.getElementById('summary-actions-list');
    actionsList.innerHTML = (data.urgent_action_items || []).map(a => `<li>${escapeHtml(a)}</li>`).join('');
  } catch (err) {
    narrativeElem.textContent = 'Error generating accreditation summary: ' + err.message;
  }
}

// Wire up event listeners
document.addEventListener('DOMContentLoaded', () => {
  // Modal close handlers
  document.getElementById('btn-close-rewrite')?.addEventListener('click', () => {
    document.getElementById('ai-rewrite-modal').classList.add('hidden');
  });
  document.getElementById('btn-close-generate')?.addEventListener('click', () => {
    document.getElementById('ai-generate-modal').classList.add('hidden');
  });
  document.getElementById('btn-close-summary')?.addEventListener('click', () => {
    document.getElementById('ai-summary-modal').classList.add('hidden');
  });

  // Action button clicks
  document.getElementById('btn-run-ai-rewrite')?.addEventListener('click', runAIRewrite);
  document.getElementById('btn-apply-rewrite')?.addEventListener('click', applyAIRewrite);
  document.getElementById('btn-run-ai-generate')?.addEventListener('click', runAIGenerateQuestions);
  document.getElementById('btn-ai-summary')?.addEventListener('click', openAIModerationSummary);
});
