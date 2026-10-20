import math
from typing import List, Dict, Any, Optional
from backend.models import (
    Syllabus, QuestionPaper, PreviousYearQuestion,
    AuditReport, AuditFinding, UnitCoverageStat,
    BloomsDistributionStat, ScoreBreakdown, QuestionItem
)
from backend.engine.semantic_mapper import SemanticMapper
from backend.engine.blooms_classifier import classify_blooms_taxonomy, BLOOMS_ORDER
from backend.engine.similarity_detector import SimilarityDetector

class ExamAuditor:
    def __init__(self, syllabus: Syllabus, paper: QuestionPaper, pyqs: Optional[List[PreviousYearQuestion]] = None):
        self.syllabus = syllabus
        self.paper = paper
        self.pyqs = pyqs or []
        self.mapper = SemanticMapper(syllabus)
        self.similarity_detector = SimilarityDetector(self.pyqs)

    def run_full_audit(self) -> AuditReport:
        """Executes the full automated examination quality audit."""
        # Step 1: Semantic Unit & Learning Outcome Mapping
        self.paper.questions = self.mapper.map_questions(self.paper.questions)

        # Step 2: Bloom's Taxonomy Cognitive Classification
        for q in self.paper.questions:
            if not q.blooms_level:
                level, verb, _ = classify_blooms_taxonomy(q.question_text)
                q.blooms_level = level
                q.command_verb = verb

        # Step 3: Previous Year Repetition Analysis
        self.paper.questions, rep_findings = self.similarity_detector.check_repetitions(self.paper.questions)

        # Step 4: Calculate Metrics, Coverages, and Findings
        return self._generate_report(rep_findings)

    def recalculate_with_overrides(self, updated_questions: List[QuestionItem]) -> AuditReport:
        """Recalculates coverage and scores after faculty overrides/edits."""
        self.paper.questions = updated_questions
        # Re-check PYQ similarities
        self.paper.questions, rep_findings = self.similarity_detector.check_repetitions(self.paper.questions)
        return self._generate_report(rep_findings)

    def _generate_report(self, rep_findings: List[AuditFinding]) -> AuditReport:
        findings: List[AuditFinding] = list(rep_findings)
        total_exam_marks = sum(q.marks for q in self.paper.questions) or 100.0
        num_units = len(self.syllabus.units) or 1
        expected_weightage_per_unit = 100.0 / num_units

        # --- Unit Coverage Analysis ---
        unit_stats: List[UnitCoverageStat] = []
        covered_units_count = 0
        weightage_deviations = []

        all_mapped_los = set()
        for q in self.paper.questions:
            for lo in q.mapped_outcomes:
                all_mapped_los.add(lo)

        total_syllabus_los = sum(len(u.learning_outcomes) for u in self.syllabus.units) or 1

        for unit in self.syllabus.units:
            unit_qs = [q for q in self.paper.questions if q.mapped_unit == unit.unit_number]
            unit_marks = sum(q.marks for q in unit_qs)
            marks_pct = (unit_marks / total_exam_marks) * 100.0 if total_exam_marks > 0 else 0.0
            
            exp_weight = unit.recommended_weightage_percent or expected_weightage_per_unit
            weightage_deviations.append(abs(marks_pct - exp_weight))

            # Coverage Status Logic
            if len(unit_qs) == 0:
                status = "Not Assessed"
                findings.append(AuditFinding(
                    finding_id=f"COV_U{unit.unit_number}",
                    category="Coverage",
                    severity="High",
                    title=f"Unit {unit.unit_number} Not Assessed",
                    message=(
                        f"Unit {unit.unit_number} (\"{unit.title}\") has {len(unit.topics)} syllabus topics "
                        f"but receives 0 marks in this question paper."
                    ),
                    related_units=[unit.unit_number],
                    related_questions=[],
                    recommended_action=f"Add at least one question evaluating core topics of {unit.title}."
                ))
            elif marks_pct < (exp_weight * 0.5):
                status = "Underrepresented"
                covered_units_count += 1
                findings.append(AuditFinding(
                    finding_id=f"WGT_LOW_U{unit.unit_number}",
                    category="Weightage",
                    severity="Medium",
                    title=f"Unit {unit.unit_number} Underrepresented",
                    message=(
                        f"Unit {unit.unit_number} (\"{unit.title}\") accounts for only {round(marks_pct, 1)}% "
                        f"of the total marks (expected ~{round(exp_weight, 1)}%)."
                    ),
                    related_units=[unit.unit_number],
                    related_questions=[q.question_id for q in unit_qs],
                    recommended_action=f"Consider increasing marks or adding a sub-question for Unit {unit.unit_number}."
                ))
            elif marks_pct > (exp_weight * 1.6):
                status = "Overrepresented"
                covered_units_count += 1
                findings.append(AuditFinding(
                    finding_id=f"WGT_HIGH_U{unit.unit_number}",
                    category="Weightage",
                    severity="Medium",
                    title=f"Unit {unit.unit_number} Overrepresented",
                    message=(
                        f"Unit {unit.unit_number} (\"{unit.title}\") receives {round(marks_pct, 1)}% of total marks "
                        f"({unit_marks} Marks), exceeding recommended weightage of {round(exp_weight, 1)}%."
                    ),
                    related_units=[unit.unit_number],
                    related_questions=[q.question_id for q in unit_qs],
                    recommended_action="Redistribute marks or questions towards underrepresented units."
                ))
            else:
                status = "Well Covered"
                covered_units_count += 1

            unit_stats.append(UnitCoverageStat(
                unit_number=unit.unit_number,
                unit_title=unit.title,
                topics_count=len(unit.topics),
                questions_count=len(unit_qs),
                total_marks=unit_marks,
                marks_percentage=round(marks_pct, 1),
                expected_weightage_percent=round(exp_weight, 1),
                coverage_status=status
            ))

        # --- Bloom's Taxonomy Cognitive Balance Analysis ---
        blooms_map = {lvl: {"marks": 0.0, "count": 0} for lvl in BLOOMS_ORDER}
        for q in self.paper.questions:
            lvl = q.blooms_level or "Understand"
            if lvl not in blooms_map:
                lvl = "Understand"
            blooms_map[lvl]["marks"] += q.marks
            blooms_map[lvl]["count"] += 1

        blooms_stats: List[BloomsDistributionStat] = []
        lower_order_marks = blooms_map["Remember"]["marks"] + blooms_map["Understand"]["marks"]
        higher_order_marks = (
            blooms_map["Apply"]["marks"] +
            blooms_map["Analyze"]["marks"] +
            blooms_map["Evaluate"]["marks"] +
            blooms_map["Create"]["marks"]
        )
        lower_order_pct = (lower_order_marks / total_exam_marks) * 100.0 if total_exam_marks > 0 else 0.0

        for lvl in BLOOMS_ORDER:
            m = blooms_map[lvl]["marks"]
            pct = (m / total_exam_marks) * 100.0 if total_exam_marks > 0 else 0.0
            blooms_stats.append(BloomsDistributionStat(
                level=lvl,
                marks=m,
                percentage=round(pct, 1),
                question_count=blooms_map[lvl]["count"]
            ))

        if lower_order_pct > 65.0:
            findings.append(AuditFinding(
                finding_id="BLM_LOWER_ORDER_HEAVY",
                category="Blooms",
                severity="High",
                title="Excessive Recall / Rote Learning Bias",
                message=(
                    f"{round(lower_order_pct, 1)}% of exam marks test Remember/Understand levels. "
                    f"Only {round(100 - lower_order_pct, 1)}% tests application or higher-order analytical reasoning."
                ),
                related_units=[],
                related_questions=[q.question_id for q in self.paper.questions if q.blooms_level in ["Remember", "Understand"]],
                recommended_action="Convert some definitions into applied problem-solving or case-based questions."
            ))
        elif higher_order_marks < (total_exam_marks * 0.25):
            findings.append(AuditFinding(
                finding_id="BLM_HIGHER_ORDER_DEFICIT",
                category="Blooms",
                severity="Medium",
                title="Deficit in Higher-Order Cognitive Testing",
                message="Less than 25% of marks evaluate Apply, Analyze, or Evaluate cognitive levels.",
                related_units=[],
                related_questions=[],
                recommended_action="Introduce algorithmic analysis or design evaluation problems."
            ))

        # --- Out-of-Syllabus Analysis ---
        out_of_syllabus_count = 0
        for q in self.paper.questions:
            if q.is_out_of_syllabus:
                out_of_syllabus_count += 1
                findings.append(AuditFinding(
                    finding_id=f"OOS_{q.question_id}",
                    category="Out-of-Syllabus",
                    severity="High",
                    title=f"Potential Out-of-Syllabus Item ({q.question_id})",
                    message=(
                        f"Question {q.question_id} (\"{(q.question_text[:75])}...\") shows weak semantic correlation "
                        f"with approved syllabus topics. {q.out_of_syllabus_reason or ''}"
                    ),
                    related_units=[],
                    related_questions=[q.question_id],
                    recommended_action="Faculty moderation required: verify if this topic is covered under prescribed curriculum."
                ))

        # --- Scoring Engine (Transparent 0-100 Calculation) ---
        # 1. Syllabus Coverage (25%): Percentage of units covered (at least 1 question)
        cov_score = (covered_units_count / num_units) * 100.0

        # 2. Learning Outcomes (20%): Percentage of declared LOs tested
        lo_score = (len(all_mapped_los) / total_syllabus_los) * 100.0 if total_syllabus_los > 0 else 80.0
        lo_score = min(100.0, lo_score * 1.2) # modest normalization

        # 3. Marks Distribution Balance (20%): Average deviation from expected weightage
        avg_deviation = sum(weightage_deviations) / len(weightage_deviations) if weightage_deviations else 0.0
        marks_score = max(0.0, 100.0 - (avg_deviation * 2.5))

        # 4. Cognitive Level / Bloom's Balance (15%): Optimal zone is 35-50% lower, 50-65% higher
        if 30.0 <= lower_order_pct <= 60.0:
            blooms_score = 95.0
        elif lower_order_pct < 30.0:
            blooms_score = 80.0
        else: # overly lower-order heavy
            blooms_score = max(40.0, 100.0 - (lower_order_pct - 50.0) * 1.6)

        # 5. Out-of-Syllabus Cleanliness (10%): Deduct 25 points per out-of-syllabus question
        oos_score = max(0.0, 100.0 - (out_of_syllabus_count * 25.0))

        # 6. Repetition Risk Cleanliness (10%): Deduct for high repeats
        high_repeats = sum(1 for q in self.paper.questions if (q.pyq_similarity or 0) >= 0.85)
        med_repeats = sum(1 for q in self.paper.questions if 0.70 <= (q.pyq_similarity or 0) < 0.85)
        rep_score = max(0.0, 100.0 - (high_repeats * 30.0 + med_repeats * 12.0))

        # Weighted Overall Score
        overall = (
            (cov_score * 0.25) +
            (lo_score * 0.20) +
            (marks_score * 0.20) +
            (blooms_score * 0.15) +
            (oos_score * 0.10) +
            (rep_score * 0.10)
        )
        overall_score = round(min(100.0, max(0.0, overall)), 1)

        # Grading
        if overall_score >= 90:
            grade = "A+ (Exemplary)"
            verdict = "Paper exhibits rigorous alignment, excellent cognitive balance, and comprehensive syllabus coverage."
        elif overall_score >= 80:
            grade = "A (High Quality)"
            verdict = "Strong assessment quality with minor adjustments recommended in marks distribution or Bloom's balance."
        elif overall_score >= 70:
            grade = "B (Fair - Review Recommended)"
            verdict = "Assessment has notable coverage gaps, mark imbalances, or cognitive skew that should be reviewed before approval."
        elif overall_score >= 60:
            grade = "C (Marginal - Revisions Required)"
            verdict = "Significant syllabus gaps, repetition risk, or heavy recall bias detected. Moderation committee action required."
        else:
            grade = "Needs Urgent Revision"
            verdict = "Paper fails several assessment-quality benchmarks. Major restructuring of units and questions required."

        return AuditReport(
            overall_quality_score=overall_score,
            grade=grade,
            verdict_summary=verdict,
            score_breakdown=ScoreBreakdown(
                syllabus_coverage_score=round(cov_score, 1),
                learning_outcomes_score=round(lo_score, 1),
                marks_distribution_score=round(marks_score, 1),
                blooms_cognitive_score=round(blooms_score, 1),
                out_of_syllabus_score=round(oos_score, 1),
                repetition_risk_score=round(rep_score, 1)
            ),
            syllabus_summary={
                "course_name": self.syllabus.course_name,
                "course_code": self.syllabus.course_code,
                "total_units": len(self.syllabus.units),
                "total_topics": sum(len(u.topics) for u in self.syllabus.units),
                "total_learning_outcomes": total_syllabus_los
            },
            paper_summary={
                "paper_title": self.paper.paper_title,
                "total_questions": len(self.paper.questions),
                "total_marks": total_exam_marks,
                "covered_units": covered_units_count,
                "unassessed_units": num_units - covered_units_count
            },
            unit_coverage=unit_stats,
            blooms_distribution=blooms_stats,
            findings=findings,
            mapped_questions=self.paper.questions
        )
