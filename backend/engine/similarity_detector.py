from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from backend.models import QuestionItem, PreviousYearQuestion, AuditFinding

class SimilarityDetector:
    def __init__(self, past_questions: List[PreviousYearQuestion]):
        self.past_questions = past_questions
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 3),
            stop_words='english',
            token_pattern=r'(?u)\b[a-zA-Z0-9_\-\./]{2,}\b'
        )
        self._build_index()

    def _build_index(self):
        if not self.past_questions:
            self.pyq_tfidf = None
            return

        texts = [q.question_text for q in self.past_questions]
        self.pyq_tfidf = self.vectorizer.fit_transform(texts)

    def check_repetitions(self, current_questions: List[QuestionItem], similarity_threshold: float = 0.70) -> Tuple[List[QuestionItem], List[AuditFinding]]:
        """
        Compares current examination questions against past year questions.
        Returns: (annotated_questions, repetition_findings)
        """
        findings: List[AuditFinding] = []
        if not self.past_questions or self.pyq_tfidf is None:
            return current_questions, findings

        curr_texts = [q.question_text for q in current_questions]
        curr_tfidf = self.vectorizer.transform(curr_texts)
        sim_matrix = cosine_similarity(curr_tfidf, self.pyq_tfidf)

        for i, q in enumerate(current_questions):
            sims = sim_matrix[i]
            best_idx = int(np.argmax(sims))
            max_sim = float(sims[best_idx])
            matched_pyq = self.past_questions[best_idx]

            q.pyq_similarity = round(max_sim, 2)
            q.pyq_matched_question = f"{matched_pyq.paper_year} ({matched_pyq.question_id}): {matched_pyq.question_text[:80]}..."

            if max_sim >= 0.85:
                findings.append(AuditFinding(
                    finding_id=f"REP_{q.question_id}",
                    category="Repetition",
                    severity="High",
                    title=f"Critical Question Repetition ({round(max_sim*100)}% match)",
                    message=(
                        f"Question {q.question_id} is nearly identical to {matched_pyq.paper_year} {matched_pyq.question_id} "
                        f"(\"{matched_pyq.question_text}\"). "
                        f"Students may have memorized past solutions."
                    ),
                    related_units=[q.mapped_unit] if q.mapped_unit else [],
                    related_questions=[q.question_id],
                    recommended_action="Paraphrase scenario, change constraints/parameters, or replace with a fresh question."
                ))
            elif max_sim >= similarity_threshold:
                findings.append(AuditFinding(
                    finding_id=f"REP_{q.question_id}",
                    category="Repetition",
                    severity="Medium",
                    title=f"Moderate Question Overlap ({round(max_sim*100)}% match)",
                    message=(
                        f"Question {q.question_id} shares significant conceptual and phrasing overlap with "
                        f"{matched_pyq.paper_year} {matched_pyq.question_id} (\"{matched_pyq.question_text}\")."
                    ),
                    related_units=[q.mapped_unit] if q.mapped_unit else [],
                    related_questions=[q.question_id],
                    recommended_action="Verify if testing the exact same problem is intentional."
                ))

        return current_questions, findings
