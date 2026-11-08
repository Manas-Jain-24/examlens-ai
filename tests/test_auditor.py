import unittest
from backend.models import (
    Syllabus, SyllabusUnit, QuestionPaper, QuestionItem, PreviousYearQuestion
)
from backend.engine.auditor import ExamAuditor
from backend.engine.blooms_classifier import classify_blooms_taxonomy

class TestAuditor(unittest.TestCase):
    def setUp(self):
        self.syllabus = Syllabus(
            course_name="Data Structures",
            course_code="CS201",
            units=[
                SyllabusUnit(
                    unit_number=1,
                    title="Linear Structures",
                    topics=["Arrays", "Linked Lists", "Stacks", "Queues"],
                    learning_outcomes=["Understand arrays and linked lists"]
                ),
                SyllabusUnit(
                    unit_number=2,
                    title="Non-Linear Trees",
                    topics=["Binary Trees", "BST", "AVL Trees"],
                    learning_outcomes=["Construct and balance trees"]
                ),
                SyllabusUnit(
                    unit_number=3,
                    title="Graph Algorithms",
                    topics=["BFS", "DFS", "Dijkstra", "Prim"],
                    learning_outcomes=["Implement graph traversals"]
                )
            ]
        )

    def test_blooms_classification(self):
        """Test Bloom's level identification."""
        level, verb, conf = classify_blooms_taxonomy("Define an array and state its advantages.")
        self.assertEqual(level, "Remember")
        self.assertEqual(verb, "define")

        level, verb, conf = classify_blooms_taxonomy("Compare and contrast BFS and DFS algorithms.")
        self.assertEqual(level, "Analyze")

        level, verb, conf = classify_blooms_taxonomy("Design a custom memory-efficient cache data structure.")
        self.assertEqual(level, "Create")

    def test_unassessed_unit_detection(self):
        """Test that omitting Unit 3 generates a High severity finding."""
        paper = QuestionPaper(
            paper_title="Mid-term Test",
            course_code="CS201",
            total_marks=20.0,
            questions=[
                QuestionItem(question_id="Q1", section="Part A", question_text="Explain linked lists", marks=10.0),
                QuestionItem(question_id="Q2", section="Part A", question_text="Construct an AVL tree", marks=10.0)
            ]
        )
        auditor = ExamAuditor(self.syllabus, paper)
        report = auditor.run_full_audit()

        # Check that Unit 3 is flagged as Not Assessed
        u3_stat = next(u for u in report.unit_coverage if u.unit_number == 3)
        self.assertEqual(u3_stat.coverage_status, "Not Assessed")
        self.assertTrue(any("Unit 3 Not Assessed" in f.title for f in report.findings))

    def test_repetition_detector(self):
        """Test that identical past question is flagged as Repetition."""
        pyqs = [
            PreviousYearQuestion(
                paper_year="2024",
                question_id="Q1",
                question_text="Explain Dijkstra's shortest path algorithm with time complexity.",
                marks=10.0
            )
        ]
        paper = QuestionPaper(
            paper_title="Draft Exam",
            course_code="CS201",
            total_marks=10.0,
            questions=[
                QuestionItem(
                    question_id="Q1",
                    section="Part A",
                    question_text="Explain Dijkstra's shortest path algorithm with time complexity.",
                    marks=10.0
                )
            ]
        )
        auditor = ExamAuditor(self.syllabus, paper, pyqs=pyqs)
        report = auditor.run_full_audit()

        # High repetition risk score deduction
        rep_finding = next((f for f in report.findings if f.category == "Repetition"), None)
        self.assertIsNotNone(rep_finding)
        self.assertEqual(rep_finding.severity, "High")

if __name__ == "__main__":
    unittest.main()
