# ExamLens AI  
### Intelligent Examination Quality and Syllabus-Alignment Auditor

ExamLens AI is an assessment-quality assurance platform engineered for educators, examination cells, academic moderation committees, and accreditation bodies (NBA, ABET, NAAC). It automates the review of draft examination papers against course syllabi and historical question papers.

---

## Key Features

1. **Syllabus & Learning Outcome Ingestion**:
   - Parses units, topics, subtopics, and course learning outcomes (COs/LOs) from PDF or structured text.
2. **Syllabus-to-Question Semantic Mapping**:
   - Uses TF-IDF n-grams + cosine similarity with keyword boosting to map every question to its corresponding syllabus unit and learning outcome.
3. **Bloom’s Taxonomy Classification**:
   - Categorizes questions across the 6 cognitive levels: *Remember*, *Understand*, *Apply*, *Analyze*, *Evaluate*, and *Create*.
   - Evaluates cognitive balance and flags rote-learning bias.
4. **Unit-Wise Coverage Matrix**:
   - Visualizes unit-by-unit representation (*Well Covered*, *Overrepresented*, *Underrepresented*, or *Not Assessed*).
5. **Mark-Weightage Balance Audit**:
   - Compares actual marks against expected weightage and flags disproportionate allocation.
6. **Out-of-Syllabus Question Detection**:
   - Flags questions with poor semantic alignment or unapproved domain concepts.
7. **Previous-Year Question (PYQ) Repetition Detector**:
   - Identifies exact repeats (>85% similarity) and concept overlap (>70% similarity).
8. **Transparent Exam Quality Score (0–100)**:
   - Explainable breakdown: Coverage (25%), Outcomes (20%), Marks Balance (20%), Bloom's Balance (15%), Out-of-Syllabus (10%), Repetition (10%).
9. **Human-in-the-Loop Faculty Review**:
   - Faculty can override mapped units or cognitive levels directly on the dashboard table, with instant recalculation of metrics and scores.
10. **Institutional PDF Audit Report Export**:
    - Generates downloadable, print-ready PDF audit certificates with findings and recommendations.

---

## Project Structure

```
Project_2/
├── backend/
│   ├── app.py                      # FastAPI REST application
│   ├── models.py                   # Pydantic data schemas
│   ├── engine/
│   │   ├── auditor.py              # Core audit orchestrator & quality scoring
│   │   ├── blooms_classifier.py    # Bloom's taxonomy verb ontology & heuristics
│   │   ├── semantic_mapper.py      # TF-IDF unit/LO mapper & out-of-syllabus engine
│   │   ├── similarity_detector.py  # Previous-year question repetition detector
│   │   ├── parsers.py              # PDF and text document extraction
│   │   └── pdf_generator.py        # ReportLab institutional PDF exporter
│   └── data/                       # Pre-loaded CS201 demo data
├── frontend/
│   ├── index.html                  # Review dashboard HTML
│   ├── styles.css                  # Custom modern design system
│   └── app.js                      # Chart.js radar & bar charts, interactive review
├── sample_documents/               # Sample syllabus, question paper, and PYQ files
├── run.py                          # One-click launcher script
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Requirements
- Python 3.10+
- Installed dependencies:
```bash
pip install -r requirements.txt
```

### 2. Launch the Application
Simply run:
```bash
python run.py
```
This starts the local FastAPI server at `http://127.0.0.1:8000` and automatically opens the review dashboard in your default browser.

### 3. Immediate Testing
- Click **"Load CS201 Demo"** to see an immediate assessment of a Data Structures final exam with real-world issues (Unit 4 graph algorithms missing, Unit 1 overrepresented, repeated 2025 question, and out-of-syllabus red-black tree).
- Or click **"Audit New Paper"** to upload or paste custom course syllabi and question papers.
