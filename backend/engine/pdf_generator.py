import io
from html import escape
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from backend.models import AuditReport

def generate_pdf_report(report: AuditReport) -> bytes:
    """Generates an institutional PDF audit report using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E293B'),
        alignment=TA_CENTER
    )
    subtitle_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#64748B'),
        alignment=TA_CENTER
    )
    h2_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#334155')
    )
    bold_body = ParagraphStyle(
        'BoldBody',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    elements = []

    # Title & Header
    elements.append(Paragraph("ExamLens AI - Assessment Quality Audit Report", title_style))
    elements.append(Paragraph("Autonomous Examination Syllabus-Alignment & Cognitive Balance Verification", subtitle_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#4F46E5'), spaceAfter=12))

    # Meta Info Table
    meta_data = [
        [
            Paragraph(f"<b>Course:</b> {escape(str(report.syllabus_summary.get('course_name', 'N/A')))} ({escape(str(report.syllabus_summary.get('course_code', '')))})", body_style),
            Paragraph(f"<b>Total Questions:</b> {report.paper_summary.get('total_questions', 0)}", body_style)
        ],
        [
            Paragraph(f"<b>Paper Title:</b> {escape(str(report.paper_summary.get('paper_title', 'Draft Paper')))}", body_style),
            Paragraph(f"<b>Expected Attempt Marks:</b> {report.paper_summary.get('total_marks', 0)} M", body_style)
        ],
        [
            Paragraph(f"<b>Syllabus Units:</b> {report.syllabus_summary.get('total_units', 0)} Units | {report.syllabus_summary.get('total_topics', 0)} Topics", body_style),
            Paragraph(f"<b>Audit Date:</b> Automated Review", body_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[320, 220])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 12))

    summary = report.paper_summary
    elements.append(Paragraph(escape(str(summary.get('choice_basis', 'All questions compulsory.'))), body_style))
    elements.append(Paragraph(f"Printed marks: {summary.get('printed_marks', summary.get('total_marks'))}. "
        f"Valid attempt marks: {summary.get('minimum_attempt_marks', summary.get('total_marks'))} - "
        f"{summary.get('maximum_attempt_marks', summary.get('total_marks'))}. "
        f"Guaranteed units: {summary.get('guaranteed_units', summary.get('covered_units'))}.", body_style))
    elements.append(Paragraph('Faculty review aid only. This report does not certify accreditation compliance.', body_style))
    elements.append(Spacer(1, 8))

    # Quality Score Card Box
    score_val = report.overall_quality_score
    score_color = colors.HexColor('#16A34A') if score_val >= 80 else (colors.HexColor('#D97706') if score_val >= 70 else colors.HexColor('#DC2626'))
    
    score_box_data = [
        [
            Paragraph(f"<font size=24 color='{score_color.hexval()}'><b>{score_val} / 100</b></font><br/><b>Overall Exam Quality Score</b>", ParagraphStyle('Score', alignment=TA_CENTER, leading=27, fontSize=10)),
            Paragraph(f"<b>Quality Grade:</b> {escape(report.grade)}<br/><br/><b>Executive Verdict:</b> {escape(report.verdict_summary)}", body_style)
        ]
    ]
    score_table = Table(score_box_data, colWidths=[200, 340])
    score_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
        ('BOX', (0,0), (-1,-1), 1.5, score_color),
        ('ALIGN', (0,0), (0,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(score_table)
    elements.append(Spacer(1, 12))

    # Score Breakdown Sub-Scores
    elements.append(Paragraph("Transparent Quality Score Breakdown", h2_style))
    sb = report.score_breakdown
    breakdown_data = [["Criterion", "Target Weight", "Score (0-100)", "Weighted Contribution"]]
    for key, label, value in [
        ('coverage', 'Guaranteed Unit Coverage', sb.syllabus_coverage_score),
        ('outcomes', 'Learning Outcomes Alignment', sb.learning_outcomes_score),
        ('marks', 'Marks Distribution Balance', sb.marks_distribution_score),
        ('blooms', "Bloom's Target Alignment", sb.blooms_cognitive_score),
        ('syllabus', 'Out-of-Syllabus Cleanliness', sb.out_of_syllabus_score),
        ('repetition', 'Repetition Risk Cleanliness', sb.repetition_risk_score),
    ]:
        weight = report.rules.component_weights[key]
        breakdown_data.append([label, f'{weight:g}%', f'{value}%', f'{value * weight / 100:.1f} pts'])
    breakdown_data.append(['TOTAL EVALUATION', '100%', '', f'{score_val} / 100'])
    breakdown_table = Table(breakdown_data, colWidths=[180, 100, 120, 140], repeatRows=1)
    breakdown_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8.5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 4),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.HexColor('#F8FAFC')]),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#E2E8F0')),
    ]))
    elements.append(breakdown_table)
    elements.append(Spacer(1, 14))

    # Unit Coverage Table
    elements.append(Paragraph("Syllabus Unit-Wise Coverage & Mark Weightage Audit", h2_style))
    unit_rows = [["Unit", "Title", "Topics", "Questions", "Marks", "Actual %", "Expected %", "Status"]]
    for u in report.unit_coverage:
        status_color = "#16A34A" if u.coverage_status == "Well Covered" else ("#DC2626" if u.coverage_status == "Not Assessed" else "#D97706")
        unit_rows.append([
            f"Unit {u.unit_number}",
            Paragraph(escape(u.unit_title), body_style),
            str(u.topics_count),
            str(u.questions_count),
            f"{u.total_marks}M",
            f"{u.marks_percentage}%",
            f"{u.expected_weightage_percent}%",
            Paragraph(f"<font color='{status_color}'><b>{u.coverage_status}</b></font>", body_style)
        ])
    unit_table = Table(unit_rows, colWidths=[35, 145, 35, 45, 45, 50, 55, 130], repeatRows=1)
    unit_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#334155')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (2,1), (6,-1), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    elements.append(unit_table)
    for unit in report.unit_coverage:
        elements.append(Paragraph(f'Unit {unit.unit_number}: guaranteed {unit.guaranteed_marks:g} marks; possible {unit.possible_marks:g} marks.', body_style))
    elements.append(Spacer(1, 14))

    # Bloom's Cognitive Distribution
    elements.append(Paragraph("Bloom's Taxonomy Cognitive Distribution", h2_style))
    blooms_rows = [["Cognitive Level", "Questions Count", "Allocated Marks", "Percentage of Exam"]]
    for b in report.blooms_distribution:
        blooms_rows.append([b.level, str(b.question_count), f"{b.marks} Marks", f"{b.percentage}%"])
    blooms_table = Table(blooms_rows, colWidths=[150, 120, 130, 140])
    blooms_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#475569')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8.5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    elements.append(blooms_table)
    elements.append(Paragraph('Bloom targets (%): ' + escape(', '.join(f'{key}: {value:g}' for key, value in report.rules.blooms_targets.items())), body_style))
    elements.append(Paragraph(f'Repetition thresholds: medium {report.rules.repeat_medium:g}; high {report.rules.repeat_high:g}.', body_style))
    elements.append(Spacer(1, 14))

    # Findings & Faculty Recommendations
    if report.findings:
        elements.append(Paragraph("Audit Findings & Actionable Moderation Directives", h2_style))
        for f in report.findings:
            sev_color = "#DC2626" if f.severity == "High" else ("#D97706" if f.severity == "Medium" else "#3B82F6")
            f_box_data = [
                [
                    Paragraph(f"<font color='{sev_color}'><b>[{escape(f.severity.upper())} SEVERITY] {escape(f.title)}</b></font> ({escape(f.category)})", bold_body),
                ],
                [
                    Paragraph(f"<b>Issue:</b> {escape(f.message)}", body_style)
                ],
                [
                    Paragraph(f"<b>Recommended Action:</b> {escape(f.recommended_action)}", body_style)
                ]
            ]
            f_table = Table(f_box_data, colWidths=[540])
            f_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FFFBEB') if f.severity == 'Medium' else colors.HexColor('#FEF2F2')),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor(sev_color)),
                ('PADDING', (0,0), (-1,-1), 4),
            ]))
            elements.append(f_table)
            elements.append(Spacer(1, 6))

    elements.append(Paragraph('Mapping Evidence & Faculty Review', h2_style))
    for q in report.mapped_questions:
        evidence = q.mapping_evidence
        text = (f'{q.question_id}: {q.question_text}\n'
                f'Suggested unit: {evidence.get("suggested_unit", "N/A")}; selected unit: {q.mapped_unit}. '
                f'Topics: {", ".join(evidence.get("matched_topics", [])) or "No direct match"}. '
                f'Cosine similarity: {evidence.get("cosine_similarity", "N/A")}. '
                f'Bloom: {q.blooms_level}; verb: {q.command_verb or "N/A"}. '
                f'Review: {q.review_status}. {q.review_note}')
        elements.append(Paragraph(escape(text).replace('\n', '<br/>'), body_style))
        elements.append(Spacer(1, 8))
    # Build PDF
    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.drawString(36, 20, 'ExamLens AI - faculty review aid')
        canvas.drawRightString(576, 20, f'Page {document.page}')
        canvas.restoreState()
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return buffer.getvalue()
