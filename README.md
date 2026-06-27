# Code7to 🚀
AI-powered code editor for beginners.

## Quick Start
```bash
pip install flask flask-cors requests
python app.py
# Open http://localhost:5000
```

## Page Flow
```
/ (splash) → /login → /dashboard → /editor → /dashboard
```

## API Routes
| Method | Route | What it does |
|--------|-------|--------------|
| GET | / | Splash page |
| GET | /login | Login / Guest entry |
| GET | /dashboard | Dashboard |
| GET | /editor | Code editor |
| POST | /api/run | Execute code via Piston |
| POST | /api/ai | Gemini AI assistant |
| POST | /api/explain-error | Auto error explanation |
| POST | /api/weekly-tip | AI daily tip |

## Gemini Key
Get free at https://aistudio.google.com → paste inside the Editor → 🔑 button.
Stored in localStorage — never sent to our servers.

## Supported Languages
Python · JavaScript · C · C++ · Java · HTML
