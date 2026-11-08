import re
from typing import List, Dict, Any, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.metrics.pairwise import cosine_similarity
from backend.models import Syllabus, SyllabusUnit, QuestionItem

class SemanticMapper:
    def __init__(self, syllabus: Syllabus):
        self.syllabus = syllabus
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words=sorted(set(ENGLISH_STOP_WORDS) | {
                'explain', 'define', 'describe', 'discuss', 'compare', 'analyze',
                'evaluate', 'create', 'implement', 'construct', 'write', 'state',
                'list', 'understand', 'apply', 'design', 'illustrate', 'demonstrate',
                'example', 'examples', 'question', 'following',
            }),
            token_pattern=r'(?u)\b[a-zA-Z0-9_\-\./]{2,}\b'
        )
        self._build_index()

    def _build_index(self):
        """Builds textual representations of each unit and learning outcome."""
        self.unit_documents = []
        self.unit_numbers = []
        self.unit_titles = []
        self.all_syllabus_topics = []

        for unit in self.syllabus.units:
            # Combine title, topics, and learning outcomes into a rich document
            topics_text = " ".join(unit.topics)
            los_text = " ".join(unit.learning_outcomes)
            full_unit_doc = f"{unit.title} {topics_text} {los_text} {unit.title}"
            
            self.unit_documents.append(full_unit_doc)
            self.unit_numbers.append(unit.unit_number)
            self.unit_titles.append(unit.title)
            
            for topic in unit.topics:
                self.all_syllabus_topics.append({
                    "topic": topic,
                    "unit_number": unit.unit_number
                })

        # Fit TF-IDF on all unit documents
        if self.unit_documents:
            self.unit_tfidf = self.vectorizer.fit_transform(self.unit_documents)
        else:
            self.unit_tfidf = None

    def map_question(self, question_text: str) -> Dict[str, Any]:
        """
        Maps a single question to the best matching syllabus unit and learning outcome.
        Detects if the question appears to be out-of-syllabus.
        """
        if not self.unit_documents:
            return {
                "mapped_unit": 1,
                "mapped_outcomes": [],
                "confidence": 0.5,
                "is_out_of_syllabus": False,
                "reason": "No syllabus units available"
            }

        cleaned_q = question_text.strip()
        q_vec = self.vectorizer.transform([cleaned_q])
        similarities = cosine_similarity(q_vec, self.unit_tfidf)[0]

        best_idx = int(np.argmax(similarities))
        max_sim = float(similarities[best_idx])
        mapped_unit_num = self.unit_numbers[best_idx]

        # Keyword boost check: if specific topic keywords appear in question
        keyword_hits = []
        for topic in self.all_syllabus_topics:
            t_words = [w.lower() for w in re.findall(r'\b[a-zA-Z0-9\-]+\b', topic["topic"]) if len(w) > 2 and w.lower() not in ["and", "the", "using", "for", "with"]]
            if not t_words:
                continue
            # If multi-word topic is directly in question
            if topic["topic"].lower() in cleaned_q.lower():
                keyword_hits.append(topic)
            else:
                matches = sum(1 for w in t_words if w in cleaned_q.lower())
                # If topic is 2 words and both match (e.g., 'avl tree' or 'singly linked')
                if len(t_words) <= 2 and matches == len(t_words):
                    keyword_hits.append(topic)
                # If topic is 3+ words and at least 2 (or 50%) match
                elif len(t_words) >= 3 and matches >= max(2, int(len(t_words) * 0.5)):
                    keyword_hits.append(topic)

        # Apply keyword preference before choosing an outcome, so both agree.
        if keyword_hits and not any(k['unit_number'] == mapped_unit_num for k in keyword_hits):
            mapped_unit_num = keyword_hits[0]['unit_number']
        unit_obj = next((u for u in self.syllabus.units if u.unit_number == mapped_unit_num), None)

        # Map to specific Learning Outcome within the unit
        mapped_los = []
        if unit_obj and unit_obj.learning_outcomes:
            lo_vecs = self.vectorizer.transform(unit_obj.learning_outcomes)
            lo_sims = cosine_similarity(q_vec, lo_vecs)[0]
            best_lo_idx = int(np.argmax(lo_sims))
            if lo_sims[best_lo_idx] > 0.05:
                mapped_los.append(unit_obj.learning_outcomes[best_lo_idx])

        # Confidence calculation
        confidence = min(0.98, max(0.40, max_sim * 1.5))
        if keyword_hits:
            confidence = min(0.98, confidence + 0.15)
            # If keyword hit matches a specific unit, confirm alignment
            matching_unit_hit = next((k for k in keyword_hits if k["unit_number"] == mapped_unit_num), None)
            if not matching_unit_hit and keyword_hits:
                # Prefer the exact keyword hit unit
                mapped_unit_num = keyword_hits[0]["unit_number"]
                confidence = 0.88

        # Out-of-syllabus detection thresholding
        is_out_of_syllabus = False
        reason = None

        # Check if question has low semantic match or tests topics absent from syllabus
        if not keyword_hits and max_sim < 0.20:
            is_out_of_syllabus = True
            reason = (
                f"Question mentions concepts with no direct match in the syllabus. "
                f"Highest semantic alignment was only {round(max_sim*100, 1)}%."
            )
        elif max_sim < 0.26 and len(cleaned_q.split()) > 7 and not keyword_hits:
            # Check for rare terms that do not exist anywhere in syllabus
            q_terms = set(re.findall(r'\b[a-zA-Z\-]{4,}\b', cleaned_q.lower()))
            syl_text = " ".join(self.unit_documents).lower()
            unmatched_terms = [t for t in q_terms if t not in syl_text and t not in ["explain", "implement", "algorithm", "properties", "discuss", "solve", "compare"]]
            if len(unmatched_terms) >= 2:
                is_out_of_syllabus = True
                terms_str = ", ".join(f"'{t}'" for t in unmatched_terms[:3])
                reason = f"Contains specific technical concepts ({terms_str}) absent from approved course syllabus."

        return {
            'evidence': {
                'suggested_unit': mapped_unit_num,
                'cosine_similarity': round(float(similarities[self.unit_numbers.index(mapped_unit_num)]), 4),
                'matched_topics': [k['topic'] for k in keyword_hits if k['unit_number'] == mapped_unit_num],
                'candidate_units': sorted([
                    {'unit_number': n, 'similarity': round(float(s), 4)}
                    for n, s in zip(self.unit_numbers, similarities)
                ], key=lambda c: c['similarity'], reverse=True)[:3],
                'method': 'TF-IDF cosine similarity plus topic keyword matches; not a probability.',
            },
            "mapped_unit": mapped_unit_num,
            "mapped_outcomes": mapped_los,
            "confidence": round(confidence, 2),
            "is_out_of_syllabus": is_out_of_syllabus,
            "out_of_syllabus_reason": reason
        }

    def map_questions(self, questions: List[QuestionItem]) -> List[QuestionItem]:
        """Maps an entire list of questions in-place."""
        for q in questions:
            res = self.map_question(q.question_text)
            q.mapped_unit = res["mapped_unit"]
            q.mapped_outcomes = res["mapped_outcomes"]
            q.mapping_confidence = res["confidence"]
            q.is_out_of_syllabus = res["is_out_of_syllabus"]
            q.out_of_syllabus_reason = res["out_of_syllabus_reason"]
            q.mapping_evidence = res.get('evidence', {})
        return questions
