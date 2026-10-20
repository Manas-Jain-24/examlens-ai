import io
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
        spaceAfter=6
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
    elements.append(Paragraph("ExamLens AI — Assessment Quality Audit Report", title_style))
    elements.append(Paragraph("Autonomous Examination Syllabus-Alignment & Cognitive Balance Verification", subtitle_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#4F46E5'), spaceAfter=12))

    # Meta Info Table
    meta_data = [
        [
            Paragraph(f"<b>Course:</b> {report.syllabus_summary.get('course_name', 'N/A')} ({report.syllabus_summary.get('course_code', '')})", body_style),
            Paragraph(f"<b>Total Questions:</b> {report.paper_summary.get('total_questions', 0)}", body_style)
        ],
        [
            Paragraph(f"<b>Paper Title:</b> {report.paper_summary.get('paper_title', 'Draft Paper')}", body_style),
            Paragraph(f"<b>Total Marks:</b> {report.paper_summary.get('total_marks', 0)} M", body_style)
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

    # Quality Score Card Box
    score_val = report.overall_quality_score
    score_color = colors.HexColor('#16A34A') if score_val >= 80 else (colors.HexColor('#D97706') if score_val >= 70 else colors.HexColor('#DC2626'))
    
    score_box_data = [
        [
            Paragraph(f"<font size=24 color='{score_color.hexval()}'><b>{score_val} / 100</b></font><br/><b>Overall Exam Quality Score</b>", ParagraphStyle('Score', alignment=TA_CENTER)),
            Paragraph(f"<b>Quality Grade:</b> {report.grade}<br/><br/><b>Executive Verdict:</b> {report.verdict_summary}", body_style)
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
    breakdown_data = [
        ["Criterion", "Target Weight", "Score (0-100)", "Weighted Contribution"],
        ["Syllabus Unit Coverage", "25%", f"{sb.syllabus_coverage_score}%", f"{round(sb.syllabus_coverage_score * 0.25, 1)} pts"],
        ["Learning Outcomes Alignment", "20%", f"{sb.learning_outcomes_score}%", f"{round(sb.learning_outcomes_score * 0.20, 1)} pts"],
        ["Marks Distribution Balance", "20%", f"{sb.marks_distribution_score}%", f"{round(sb.marks_distribution_score * 0.20, 1)} pts"],
        ["Bloom's Cognitive Balance", "15%", f"{sb.blooms_cognitive_score}%", f"{round(sb.blooms_cognitive_score * 0.15, 1)} pts"],
        ["Out-of-Syllabus Cleanliness", "10%", f"{sb.out_of_syllabus_score}%", f"{round(sb.out_of_syllabus_score * 0.10, 1)} pts"],
        ["Repetition Risk Cleanliness", "10%", f"{sb.repetition_risk_score}%", f"{round(sb.repetition_risk_score * 0.10, 1)} pts"],
        ["TOTAL EVALUATION", "100%", "", f"<b>{score_val} / 100</b>"]
    ]
    breakdown_table = Table(breakdown_data, colWidths=[180, 100, 120, 140])
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
            Paragraph(u.unit_title, body_style),
            str(u.topics_count),
            str(u.questions_count),
            f"{u.total_marks}M",
            f"{u.marks_percentage}%",
            f"{u.expected_weightage_percent}%",
            Paragraph(f"<font color='{status_color}'><b>{u.coverage_status}</b></font>", body_style)
        ])
    unit_table = Table(unit_rows, colWidths=[45, 145, 45, 55, 45, 55, 65, 85])
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
    elements.append(Spacer(1, 14))

    # Findings & Faculty Recommendations
    if report.findings:
        elements.append(Paragraph("Audit Findings & Actionable Moderation Directives", h2_style))
        for f in report.findings:
            sev_color = "#DC2626" if f.severity == "High" else ("#D97706" if f.severity == "Medium" else "#3B82F6")
            f_box_data = [
                [
                    Paragraph(f"<font color='{sev_color}'><b>[{f.severity.upper()} SEVERITY] {f.title}</b></font> ({f.category})", bold_body),
                ],
                [
                    Paragraph(f"<b>Issue:</b> {f.message}", body_style)
                ],
                [
                    Paragraph(f"<b>Recommended Action:</b> {f.recommended_action}", body_style)
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

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
