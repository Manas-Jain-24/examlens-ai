import unittest
from backend.engine.parsers import parse_syllabus_text, parse_question_paper_text, parse_pyq_text

class TestParsers(unittest.TestCase):
    def test_parse_syllabus(self):
        sample = """
        Subject: Data Structures and Algorithms (CS201)
        Unit 1: Linear Data Structures
        - Singly Linked Lists
        - Doubly Linked Lists
        - Stack and Queue ADTs
        CO: Implement linear lists and stacks

        Unit 2: Non-Linear Data Structures
        - Binary Trees
        - Binary Search Trees
        - AVL Trees
        CO: Construct balanced search trees
        """
        syllabus = parse_syllabus_text(sample)
        self.assertEqual(syllabus.course_code, "CS201")
        self.assertEqual(len(syllabus.units), 2)
        self.assertEqual(syllabus.units[0].unit_number, 1)
        self.assertIn("Singly Linked Lists", syllabus.units[0].topics)
        self.assertEqual(syllabus.units[1].unit_number, 2)
        self.assertTrue(len(syllabus.units[0].learning_outcomes) > 0)

    def test_parse_question_paper(self):
        sample = """
        End Semester Examination - CS201
        Section A: Short Questions
        Q1. Define an Abstract Data Type (ADT). (2 Marks)
        Q2. Differentiate between Singly and Doubly linked lists. (5 Marks)

        Section B: Long Problems
        Q3. Construct an AVL tree by inserting keys 10, 20, 30, 40, 50. Explain rotations. (10 Marks)
        """
        paper = parse_question_paper_text(sample)
        self.assertEqual(len(paper.questions), 3)
        self.assertEqual(paper.questions[0].question_id, "Q1")
        self.assertEqual(paper.questions[0].marks, 2.0)
        self.assertEqual(paper.questions[1].question_id, "Q2")
        self.assertEqual(paper.questions[1].marks, 5.0)
        self.assertEqual(paper.questions[2].question_id, "Q3")
        self.assertEqual(paper.questions[2].marks, 10.0)
        self.assertEqual(paper.total_marks, 17.0)

    def test_parse_pyq(self):
        sample = """
        Previous Year Exam - 2024
        Q1. Explain BFS and DFS algorithms with an example graph.
        Q2. Define hash collision and discuss linear probing.
        """
        pyqs = parse_pyq_text(sample, default_year="2024")
        self.assertEqual(len(pyqs), 2)
        self.assertEqual(pyqs[0].question_id, "Q1")
        self.assertIn("BFS", pyqs[0].question_text)

if __name__ == "__main__":
    unittest.main()
