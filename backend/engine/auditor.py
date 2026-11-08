import math
from typing import List, Dict, Any, Optional
from backend.models import (
    Syllabus, QuestionPaper, PreviousYearQuestion,
    AuditReport, AuditFinding, UnitCoverageStat,
    BloomsDistributionStat, ScoreBreakdown, QuestionItem, AuditRules
)
from backend.engine.choices import choice_accounting, expected_outcome_coverage, allocated_marks
from backend.engine.semantic_mapper import SemanticMapper
from backend.engine.blooms_classifier import classify_blooms_taxonomy, BLOOMS_ORDER
from backend.engine.similarity_detector import SimilarityDetector

class ExamAuditor:
    def __init__(self, syllabus: Syllabus, paper: QuestionPaper, pyqs: Optional[List[PreviousYearQuestion]] = None, rules: Optional[AuditRules] = None):
        self.syllabus = syllabus
        self.paper = paper
        self.pyqs = pyqs or []
        self.rules = rules or AuditRules()
        if self.rules.unit_weights and set(self.rules.unit_weights) != {u.unit_number for u in syllabus.units}:
            raise ValueError('Unit weights must match the syllabus units.')
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
        self.paper.questions, rep_findings = self.similarity_detector.check_repetitions(
            self.paper.questions, self.rules.repeat_medium, self.rules.repeat_high)

        # Step 4: Calculate Metrics, Coverages, and Findings
        return self._generate_report(rep_findings)

    def recalculate_with_overrides(self, updated_questions: List[QuestionItem]) -> AuditReport:
        """Recalculates coverage and scores after faculty overrides/edits."""
        self.paper.questions = updated_questions
        # Re-check PYQ similarities
        self.paper.questions, rep_findings = self.similarity_detector.check_repetitions(
            self.paper.questions, self.rules.repeat_medium, self.rules.repeat_high)
        return self._generate_report(rep_findings)

    def _generate_report(self, rep_findings: List[AuditFinding]) -> AuditReport:
        findings: List[AuditFinding] = list(rep_findings)
        selection_weights, total_exam_marks, min_marks, max_marks = choice_accounting(self.paper)
        total_exam_marks = total_exam_marks or 100.0
        effective_marks = lambda q: q.marks * selection_weights[q.question_id]
        guaranteed_units = 0
        num_units = len(self.syllabus.units) or 1
        expected_weightage_per_unit = 100.0 / num_units

        # --- Unit Coverage Analysis ---
        unit_stats: List[UnitCoverageStat] = []
        covered_units_count = 0
        weightage_deviations = []

        expected_los, total_syllabus_los = expected_outcome_coverage(self.paper, self.syllabus)

        for unit in self.syllabus.units:
            unit_qs = [q for q in self.paper.questions if allocated_marks(q, unit.unit_number) > 0]
            _, unit_marks, guaranteed, possible = choice_accounting(self.paper, unit.unit_number)
            if guaranteed > 0:
                guaranteed_units += 1
            marks_pct = (unit_marks / total_exam_marks) * 100.0 if total_exam_marks > 0 else 0.0
            
            exp_weight = self.rules.unit_weights.get(unit.unit_number,
                unit.recommended_weightage_percent if unit.recommended_weightage_percent is not None else expected_weightage_per_unit)
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

            if guaranteed == 0 and possible > 0:
                status = 'Optional Only'
            unit_stats.append(UnitCoverageStat(
                guaranteed_marks=guaranteed,
                possible_marks=possible,
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
            blooms_map[lvl]["marks"] += effective_marks(q)
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

        blooms_distance = sum(
            abs(blooms_map[level]['marks'] / total_exam_marks * 100 - self.rules.blooms_targets[level])
            for level in BLOOMS_ORDER) / 2
        if blooms_distance > 20:
            findings.append(AuditFinding(
                finding_id='BLM_TARGET_DEVIATION', category='Blooms',
                severity='High' if blooms_distance > 40 else 'Medium',
                title='Cognitive distribution differs from configured targets',
                message=f'Total variation from the selected Bloom targets is {blooms_distance:.1f} percentage points.',
                recommended_action='Review the question levels or adjust the course-specific target distribution.'
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
        cov_score = (guaranteed_units / num_units) * 100.0

        # 2. Learning Outcomes (20%): Percentage of declared LOs tested
        lo_score = expected_los / total_syllabus_los * 100.0 if total_syllabus_los else 0.0

        # 3. Marks Distribution Balance (20%): Average deviation from expected weightage
        avg_deviation = sum(weightage_deviations) / len(weightage_deviations) if weightage_deviations else 0.0
        marks_score = max(0.0, 100.0 - (avg_deviation * 2.5))

        # Total variation distance to the faculty's requested Bloom distribution.
        blooms_score = max(0.0, 100.0 - blooms_distance)

        # 5. Out-of-Syllabus Cleanliness (10%): Deduct 25 points per out-of-syllabus question
        oos_score = max(0.0, 100.0 - sum(selection_weights[q.question_id] * 25
            for q in self.paper.questions if q.is_out_of_syllabus))

        # 6. Repetition Risk Cleanliness (10%): Deduct for high repeats
        high_repeats = sum(selection_weights[q.question_id] for q in self.paper.questions if (q.pyq_similarity or 0) >= self.rules.repeat_high)
        med_repeats = sum(selection_weights[q.question_id] for q in self.paper.questions if self.rules.repeat_medium <= (q.pyq_similarity or 0) < self.rules.repeat_high)
        rep_score = max(0.0, 100.0 - (high_repeats * 30.0 + med_repeats * 12.0))

        # Weighted Overall Score
        components = dict(coverage=cov_score, outcomes=lo_score, marks=marks_score,
                          blooms=blooms_score, syllabus=oos_score, repetition=rep_score)
        components = {key: round(value, 1) for key, value in components.items()}
        overall = sum(components[key] * weight / 100 for key, weight in self.rules.component_weights.items())
        for stat in unit_stats:
            if stat.total_marks > 0 and stat.guaranteed_marks == 0:
                findings.append(AuditFinding(finding_id=f'CHOICE_U{stat.unit_number}', category='Coverage',
                    severity='High', title=f'Unit {stat.unit_number} can be skipped',
                    message='All questions for this unit are optional. Some valid student selections assess none of it.',
                    recommended_action='Add a compulsory question or revise the choice groups.', related_units=[stat.unit_number]))
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
            rules=self.rules,
            choice_groups=self.paper.choice_groups,
            syllabus=self.syllabus,
            pyqs=self.pyqs,
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
                'printed_marks': sum(q.marks for q in self.paper.questions),
                'scoring_version': '2.1',
                'minimum_attempt_marks': min_marks,
                'maximum_attempt_marks': max_marks,
                'guaranteed_units': guaranteed_units,
                'choice_basis': 'Expected marks assume uniform choice within each group; coverage score uses guaranteed units.' if self.paper.choice_groups else 'All questions compulsory.',
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
