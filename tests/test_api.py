import unittest
from fastapi.testclient import TestClient
from backend.app import app

class TestExamLensAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_check(self):
        """Verify /api/health returns 200 OK and valid health metadata."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["app"], "ExamLens AI")
        self.assertIn("version", data)

    def test_demo_audit(self):
        """Verify /api/demo returns full CS201 audit report."""
        response = self.client.get("/api/demo")
        self.assertEqual(response.status_code, 200)
        report = response.json()

        self.assertIn("overall_quality_score", report)
        self.assertIn("grade", report)
        self.assertIn("unit_coverage", report)
        self.assertIn("blooms_distribution", report)
        self.assertIn("findings", report)
        self.assertIn("mapped_questions", report)

        # Check CS201 specific values
        self.assertEqual(report["syllabus_summary"]["course_code"], "CS201")
        self.assertGreater(len(report["unit_coverage"]), 0)
        self.assertGreater(len(report["mapped_questions"]), 0)

    def test_audit_missing_payload_returns_error(self):
        """Verify submitting empty audit payload returns structured 422 error."""
        response = self.client.post("/api/audit", data={})
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertFalse(data.get("success", True))
        self.assertIn("Syllabus document", data.get("message", ""))

    def test_audit_with_pasted_text(self):
        """Verify /api/audit succeeds with valid raw syllabus and paper text."""
        syllabus_text = (
            "Course: CS101 Introduction to Computing\n"
            "Unit 1: Fundamentals of Programming\n"
            "- Variables and Types\n"
            "- Loops and Conditionals\n"
            "Unit 2: Functions and Recursion\n"
            "- Defining Functions\n"
            "- Base cases and Recursive calls\n"
        )
        paper_text = (
            "Section A\n"
            "Q1. Define a variable and list primitive types. (5 Marks)\n"
            "Q2. Write a recursive function to compute factorial of n. (10 Marks)\n"
        )
        response = self.client.post("/api/audit", data={
            "syllabus_text": syllabus_text,
            "paper_text": paper_text
        })
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertGreater(report["overall_quality_score"], 0)
        self.assertEqual(len(report["mapped_questions"]), 2)

    def test_export_pdf(self):
        """Verify /api/export-pdf generates valid PDF bytes from demo report."""
        # First get demo report
        demo_resp = self.client.get("/api/demo")
        self.assertEqual(demo_resp.status_code, 200)
        report = demo_resp.json()

        # Request PDF generation
        pdf_resp = self.client.post("/api/export-pdf", json=report)
        self.assertEqual(pdf_resp.status_code, 200)
        self.assertEqual(pdf_resp.headers["content-type"], "application/pdf")
        self.assertTrue(len(pdf_resp.content) > 1000)
        # PDF magic bytes %PDF
        self.assertTrue(pdf_resp.content.startswith(b"%PDF"))

if __name__ == "__main__":
    unittest.main()
