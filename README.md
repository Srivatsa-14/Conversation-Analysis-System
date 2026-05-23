# Conversational Analytics System

A Flask-based platform for analyzing conversations using speech recognition, NLP, and AI-powered insights.

## Prerequisites

- Python 3.10+
- [Deepgram API key](https://console.deepgram.com) (for speech recognition)
- NLP Cloud

## Setup

```bash
# 1. Create and activate virtual environment (Windows)
python -m venv venv
.\venv\Scripts\activate

# 2. Install dependencies
pip install -r req.txt

# 3. Download spaCy model
python -m spacy download en_core_web_sm

# 4. Configure environment variables
```
Edit `.env` and set:
- `DEEPGRAM_API_KEY` — your Deepgram API key (required)
- `FLASK_SECRET_KEY` — a random secret string
- `FLASK_DEBUG` — `1` to enable debug mode
- `PORT` — server port (default: 8080)
```

## Run

```bash
# Activate virtual environment (if not already active)
.\venv\Scripts\activate

# Start the server
python app.py

# Or specify a custom port
python app.py --port 5000
```

The app will be available at **http://localhost:8080**.

## Usage

1. Open the app in your browser
2. Register a new account
3. Upload an audio file (MP3, WAV, M4A, etc.)
4. View the automated analysis:
   - Transcription & speaker diarization
   - Sentiment analysis & topic detection
   - AI-generated summaries
   - Interactive charts and reports
5. Export reports as HTML or PDF

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register a new user |
| POST | `/api/auth/login` | Login |
| GET | `/api/auth/verify` | Verify auth token |
| POST | `/api/upload` | Upload audio file |
| POST | `/api/transcribe` | Full conversation analysis |
| GET | `/api/conversations` | List past conversations |
| GET | `/api/conversations/<id>` | Get conversation details |
| GET | `/api/export/<id>` | Export as HTML report |
| GET | `/api/export/<id>/pdf` | Export as PDF report |
| GET | `/api/health` | Health check |
| GET | `/api/features` | List available features |
