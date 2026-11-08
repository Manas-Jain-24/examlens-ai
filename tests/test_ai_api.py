import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app import app
from backend.models import (
    AIRewriteRequest, AIGenerateQuestionRequest, AIModerationSummaryRequest
)

class TestAIApi(unittest.TestCase):
    def setUp(self):
        # Tests must never make paid external API calls when a developer has a key.
        self.client_patch = patch('backend.engine.gemini_service.gemini_service.client', None)
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_ai_status(self):
        """Verify /api/ai/status returns active model and live AI status flag."""
        response = self.client.get("/api/ai/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("live_ai_available", data)
        self.assertIn("model", data)
        self.assertIn("has_api_key", data)

    def test_ai_rewrite_question(self):
        """Verify /api/ai/rewrite returns a higher-order rewritten question."""
        payload = {
            "question_text": "What is a binary search tree? (5 Marks)",
            "current_blooms_level": "Remember",
            "target_blooms_level": "Apply",
            "issue_reason": "Excessive recall / rote learning bias.",
            "marks": 10.0
        }
        response = self.client.post("/api/ai/rewrite", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["original_question"], payload["question_text"])
        self.assertIn("rewritten_question", data)
        self.assertTrue(len(data["rewritten_question"]) > 10)
        self.assertEqual(data["target_blooms_level"], "Apply")
        self.assertIn("pedagogical_rationale", data)
        self.assertIn("command_verb", data)

    def test_ai_generate_unit_questions(self):
        """Verify /api/ai/generate-question produces balanced candidates for an unassessed unit."""
        payload = {
            "course_name": "Data Structures",
            "course_code": "CS201",
            "unit_number": 4,
            "unit_title": "Graph Algorithms",
            "unit_topics": ["Breadth First Search (BFS)", "Depth First Search (DFS)", "Dijkstra's Shortest Path"],
            "target_blooms_level": "Analyze",
            "marks": 10.0
        }
        response = self.client.post("/api/ai/generate-question", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["unit_number"], 4)
        self.assertEqual(data["unit_title"], "Graph Algorithms")
        self.assertIn("candidates", data)
        self.assertGreater(len(data["candidates"]), 0)

        first = data["candidates"][0]
        self.assertIn("question_text", first)
        self.assertIn("command_verb", first)
        self.assertIn("marks", first)

    def test_ai_moderation_summary(self):
        """Verify /api/ai/moderation-summary synthesizes executive accreditation review."""
        # Fetch demo audit report first
        demo_resp = self.client.get("/api/demo")
        self.assertEqual(demo_resp.status_code, 200)
        report = demo_resp.json()

        response = self.client.post("/api/ai/moderation-summary", json={"report": report})
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("accreditation_summary", data)
        self.assertIn("key_strengths", data)
        self.assertIn("urgent_action_items", data)
        self.assertIn("nba_abet_readiness", data)
        self.assertGreater(len(data["key_strengths"]), 0)

if __name__ == "__main__":
    unittest.main()
