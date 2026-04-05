# Resume Screening API

A FastAPI service that predicts the most suitable job role from resume text using a **TF-IDF + BiLSTM ensemble** model. Upload a PDF, DOCX, or plain-text resume and receive a predicted role, confidence score, top-3 matches, and extracted skills.

---

## Project Structure

```
resume_screening/
├── app/                        # FastAPI application
│   ├── main.py                 # App entry point, lifespan, CORS
│   ├── core/
│   │   ├── config.py           # Settings (env-configurable)
│   │   ├── logger.py           # Centralised logging
│   │   └── security.py         # Auth stub (extend as needed)
│   ├── api/
│   │   ├── routes/
│   │   │   └── resume.py       # POST /screen and /screen/upload
│   │   ├── schemas/
│   │   │   └── resume.py       # Pydantic request/response models
│   │   └── dependencies/
│   │       └── models.py       # FastAPI dependency for ML models
│   ├── services/
│   │   ├── resume_parser.py    # PDF / DOCX / TXT text extraction
│   │   ├── skill_extractor.py  # Keyword-based skill detection
│   │   └── matcher.py          # Skill coverage scorer
│   └── utils/
│       ├── text.py             # Text cleaning / normalisation
│       └── file_handler.py     # Upload validation helper
├── ml/                         # ML inference layer
│   ├── loader.py               # Model loading & caching
│   └── predictor.py            # Ensemble prediction logic
├── ml_/                        # Training artefacts (not shipped in Docker)
│   ├── datasets/               # resume_dataset.csv
│   ├── saved_models/           # .pkl and .keras model files
│   └── training/               # Training scripts
├── tests/
│   └── test_api.py             # Pytest test suite
├── Dockerfile                  # Multi-stage production build
├── docker-compose.yml          # Local orchestration
├── .dockerignore
├── .gitignore
└── requirements.txt
```

---

## Quickstart

### 1 — Local (without Docker)

```bash
# Clone and enter the project
git clone <your-repo-url>
cd resume_screening

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000/docs** for the interactive Swagger UI.

### 2 — Docker

```bash
# Build and start
docker compose up --build

# Run in background
docker compose up -d

# Stop
docker compose down
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health check |
| `POST` | `/api/v1/resume/screen` | Screen resume from plain text |
| `POST` | `/api/v1/resume/screen/upload` | Screen resume from file upload |

### Example — Text Screening

```bash
curl -X POST http://localhost:8000/api/v1/resume/screen \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Experienced ML engineer with 5 years in Python, TensorFlow, and AWS..."
  }'
```

**Response:**
```json
{
  "predicted_role": "Machine Learning Engineer",
  "confidence": "94%",
  "top_matches": [
    "Machine Learning Engineer",
    "Data Scientist",
    "Backend Engineer"
  ],
  "extracted_skills": ["python", "tensorflow", "aws"],
  "match_score": 0.15
}
```

### Example — File Upload

```bash
curl -X POST http://localhost:8000/api/v1/resume/screen/upload \
  -F "file=@resume.pdf"
```

Supported formats: `.pdf`, `.txt`, `.docx` (max 5 MB).

---

## Configuration

All settings can be overridden with environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_DIR` | `ml_/saved_models` | Path to saved model artefacts |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `MAX_UPLOAD_SIZE_MB` | `5` | Maximum file upload size in MB |
| `PORT` | `8000` | Port the server listens on |

Set them in a `.env` file or pass via `-e` to Docker:

```bash
docker run -e LOG_LEVEL=DEBUG -e MODEL_DIR=/models -p 8000:8000 resume-screening-api
```

---

## ML Models

The ensemble uses two independent classifiers:

| Model | File | Description |
|-------|------|-------------|
| **TF-IDF + LogReg** | `tfidf_pipeline.pkl` | Fast, interpretable baseline |
| **BiLSTM** | `bilstm_model.keras` | Deep sequence model for context |
| Label encoder | `label_encoder.pkl` | Maps class indices to role names |
| Tokenizer | `tokenizer.pkl` | Word index for BiLSTM input |

Both models are optional — the API works with either or both present. The final prediction is the **average of class probabilities** across available models.

To retrain, see [`ml_/training/resume_screening.py`](ml_/training/resume_screening.py).

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use mocked ML models — no model files are required to run the test suite.

---

## Requirements

- Python 3.11+
- TensorFlow 2.15
- See [`requirements.txt`](requirements.txt) for the full list
