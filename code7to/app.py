from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
import json
import re
import os

app = Flask(__name__)
app.secret_key = "code7to-secret-change-in-prod"
CORS(app)

# ── Supabase config ──
SUPABASE_URL  = os.getenv("SUPABASE_URL",  "https://kjgqqlghlennibjofvck.supabase.co")
SUPABASE_ANON = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtqZ3FxbGdobGVubmliam9mdmNrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ5NjM0ODMsImV4cCI6MjA5MDUzOTQ4M30.ufi6GmpR5bKWJumV-nOEPvSuTBpCAtfeepMLy-54Rbs")

GEMINI_URL    = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SUPPORTED_LANGS = {"python", "javascript", "c", "cpp", "java", "html"}


# ── PAGES ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/editor")
def editor():
    return render_template("editor.html")

@app.route("/myfiles")
def myfiles():
    return render_template("myfiles.html")

@app.route("/profile")
def profile():
    return render_template("profile.html")


# ── HELPER ─────────────────────────────────────────────────────────────────

def call_gemini(api_key, prompt, max_tokens=1000, temperature=0.1):
    resp = requests.post(
        f"{GEMINI_URL}?key={api_key}",
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
        },
        timeout=30,
    )
    if resp.status_code in (400, 403):
        raise PermissionError("Invalid or expired Gemini API key.")
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


# ── API: RUN CODE via Gemini ────────────────────────────────────────────────

@app.route("/api/run", methods=["POST"])
def run_code():
    data     = request.get_json()
    code     = data.get("code", "").strip()
    language = data.get("language", "python").lower()
    stdin    = data.get("stdin", "").strip()
    api_key  = data.get("api_key", "").strip()

    if not code:
        return jsonify({"error": "No code provided"}), 400
    if language not in SUPPORTED_LANGS:
        return jsonify({"error": f"Language '{language}' not supported"}), 400
    if not api_key:
        return jsonify({"error": "No Runner API key. Set c7t_gk in localStorage."}), 401

    if language == "html":
        return jsonify({"output": "", "stderr": "", "is_html": True, "html_content": code})

    prompt = f"""You are a precise {language} code execution simulator.

Execute the following {language} code EXACTLY as a real interpreter/compiler would.

CODE:
```{language}
{code}
```
{"STDIN (feed this to the program if it reads input):\\n" + stdin if stdin else ""}

RULES:
1. Simulate execution faithfully — do not guess, invent output, or add commentary.
2. If the code has a compile/runtime error, output NOTHING to stdout and put the real error in stderr (e.g. "SyntaxError: ...", "NameError: ...").
3. For infinite loops, stop after 20 iterations and append "... (truncated after 20 iterations)" to stdout.
4. Return ONLY a JSON object — no markdown, no extra text:
{{"stdout": "the program output", "stderr": ""}}
If error: {{"stdout": "", "stderr": "ErrorType: description on line N"}}"""

    try:
        raw = call_gemini(api_key, prompt, max_tokens=800, temperature=0.0)
        raw = re.sub(r'^```json\s*', '', raw.strip())
        raw = re.sub(r'^```\s*',     '', raw.strip())
        raw = re.sub(r'\s*```$',     '', raw.strip())
        result = json.loads(raw)
        return jsonify({"output": result.get("stdout",""), "stderr": result.get("stderr",""), "is_html": False})
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except json.JSONDecodeError:
        return jsonify({"output": raw, "stderr": "", "is_html": False})
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Cannot reach Gemini. Check your internet."}), 503
    except requests.exceptions.Timeout:
        return jsonify({"error": "Gemini timed out (30s)."}), 408
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: VISUALIZE CODE via separate Gemini key ────────────────────────────

@app.route("/api/visualize", methods=["POST"])
def visualize_code():
    data     = request.get_json()
    code     = data.get("code", "").strip()
    language = data.get("language", "python").lower()
    api_key  = data.get("api_key", "").strip()

    if not code:
        return jsonify({"error": "No code provided"}), 400
    if not api_key:
        return jsonify({"error": "No Visualizer API key. Set c7t_vk in localStorage."}), 401

    prompt = f"""You are a code execution tracer for educational visualization.

Analyze this {language} code and produce a step-by-step execution trace as JSON.

Code:
```{language}
{code}
```

Return ONLY valid JSON (no markdown, no extra text) with this structure:
{{"steps":[{{"line":3,"description":"What this line does in plain English","variables":{{"name":"value"}},"arrays":[{{"name":"arr","values":[1,2,3],"highlights":[0,1],"swapped":[]}}],"callstack":[{{"fn":"main","line":1}}],"output":"any print output at this step","changed_vars":["name"]}}],"summary":"one sentence summary"}}

Rules:
- 8 to 18 steps total, focus on key moments
- For loops show first 2-3 iterations only
- variables: only those currently in scope
- highlights: array indices being accessed/compared
- swapped: indices that just swapped values
- output: cumulative stdout up to this step
- changed_vars: which vars changed THIS step"""

    try:
        raw = call_gemini(api_key, prompt, max_tokens=2500, temperature=0.1)
        raw = re.sub(r'^```json\s*', '', raw.strip())
        raw = re.sub(r'^```\s*',     '', raw.strip())
        raw = re.sub(r'\s*```$',     '', raw.strip())
        trace = json.loads(raw)
        if not trace.get("steps"):
            raise ValueError("Empty trace")
        return jsonify({"trace": trace})
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except (json.JSONDecodeError, ValueError) as e:
        return jsonify({"error": f"Could not parse trace: {e}"}), 500
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Cannot reach Gemini. Check your internet."}), 503
    except requests.exceptions.Timeout:
        return jsonify({"error": "Gemini timed out (30s)."}), 408
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: AI ASSISTANT ──────────────────────────────────────────────────────

@app.route("/api/ai", methods=["POST"])
def ai_assist():
    data     = request.get_json()
    message  = data.get("message", "")
    code     = data.get("code", "")
    language = data.get("language", "python")
    api_key  = data.get("api_key", "")
    error    = data.get("error", "")

    if not api_key:
        return jsonify({"error": "No Gemini API key provided"}), 401
    if not message:
        return jsonify({"error": "No message"}), 400

    prompt = f"""You are Code7to's AI Coding Assistant — a friendly tutor for beginners.

RULES:
1. NEVER write complete solutions or fix code for the user
2. Explain errors in simple plain English — no jargon
3. Give one specific hint pointing in the right direction
4. Keep responses under 100 words unless more is needed

Language: {language}
Code:
```{language}
{code}
```
{"Error: " + error if error else ""}

User: {message}"""

    try:
        reply = call_gemini(api_key, prompt, max_tokens=300, temperature=0.7)
        return jsonify({"reply": reply})
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: EXPLAIN ERROR ─────────────────────────────────────────────────────

@app.route("/api/explain-error", methods=["POST"])
def explain_error():
    data    = request.get_json()
    error   = data.get("error", "")
    code    = data.get("code", "")
    lang    = data.get("language", "python")
    api_key = data.get("api_key", "")

    if not api_key or not error:
        return jsonify({"reply": None})

    prompt = f"""A beginner got this {lang} error:
{error}

Their code:
```{lang}
{code}
```

In 2-3 SHORT sentences:
1. Explain what the error means simply
2. Give ONE hint about where to look
Do NOT write the fix. Be encouraging. Max 60 words."""

    try:
        reply = call_gemini(api_key, prompt, max_tokens=150, temperature=0.5)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": None, "error": str(e)})


# ── API: WEEKLY TIP ────────────────────────────────────────────────────────

@app.route("/api/weekly-tip", methods=["POST"])
def weekly_tip():
    data    = request.get_json()
    api_key = data.get("api_key", "")
    fallback = "Break big problems into smaller functions — it makes debugging 10x easier!"
    if not api_key:
        return jsonify({"tip": fallback})
    try:
        tip = call_gemini(api_key, "Give one short practical coding tip for a beginner. Max 25 words. No intro.", max_tokens=60, temperature=0.9)
        return jsonify({"tip": tip})
    except Exception:
        return jsonify({"tip": fallback})


@app.route("/groups")
def groups():
    return render_template("groups.html")


# ── API: GET API KEYS ──────────────────────────────────────────────────────

@app.route("/api/get-api-keys", methods=["GET"])
def get_api_keys():
    return jsonify({
        "runner_key": GEMINI_API_KEY,
        "viz_key": GEMINI_API_KEY
    })


# ── API: SUPABASE PING ─────────────────────────────────────────────────────

@app.route("/api/supabase-ping", methods=["GET"])
def supabase_ping():
    try:
        resp = requests.get(f"{SUPABASE_URL}/rest/v1/", headers={"apikey": SUPABASE_ANON}, timeout=5)
        return jsonify({"ok": True, "status": resp.status_code})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 503


# ── RUN ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*50)
    print("  🚀 Code7to running — http://localhost:5000")
    print("")
    print("  Set API key via environment variable:")
    print("  export GEMINI_API_KEY='YOUR_KEY'")
    print("="*50 + "\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
