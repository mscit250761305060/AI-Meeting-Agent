# AI Meeting Agent

> Autonomous AI Meeting Agent that joins online meetings, listens to discussions, understands requirements, generates complete software projects, runs them automatically, and provides a live preview.

---

## 1. Project Goal

The objective of this project is to build an AI software engineer that can replace the manual software requirement gathering process. Instead of developers attending meetings and writing notes, the AI Agent natively joins Google Meet, listens to the discussion, extracts requirements, and builds the complete project architecture (frontend, backend, database) incrementally while the meeting is still happening. 

The user only needs to provide the meeting link. Everything else happens automatically.

---

## 2. Technology Stack & Components (What drives the Agent?)

Here is a breakdown of every component inside the AI Meeting Agent and the specific technology used to run it:

### 🎙️ Audio Capture & Speech-to-Text
* **Technology:** `PyAudio`, `faster-whisper`
* **Model:** `small.en` (OpenAI Whisper)
* **Function:** Captures system audio loopback in real-time. The audio is chopped into small chunks and fed to the local Whisper model running on the CPU to generate accurate English transcripts. It uses an `initial_prompt` to properly detect technical software terms.

### 🌐 Visual Context & Meeting Automation
* **Technology:** `Playwright` (Python Async)
* **Function:** Launches a headless Chromium browser, automatically navigates to the Google Meet URL, bypasses the waiting room, mutes the mic/camera, and clicks "Join". It also takes periodic screenshots to monitor meeting events (e.g., if the bot is kicked out).

### 🧠 Requirement Extraction (The Brain)
* **Technology:** `Google Gemini API`
* **Model:** `gemini-3.1-flash-lite` (or `gemini-2.0-flash`)
* **Function:** When there is a 15-second pause in conversation, the transcript is sent to the Gemini API. Gemini acts as a Business Analyst, extracting features, required pages, and database models into a structured `requirements.json` file. It automatically deduplicates similar pages.

### ⚙️ Autonomous Code Generation
* **Technology:** `Google Gemini API`, `concurrent.futures` (Parallel Processing)
* **Function:**
  - **Backend Generation:** Writes Python code for `FastAPI` and `SQLAlchemy` (database.py, models.py, schemas.py, crud.py, app.py).
  - **Database Seeding:** Automatically creates fake demo records in the SQLite database.
  - **Frontend Generation:** Uses `ThreadPoolExecutor` to generate all Vanilla HTML/CSS/JS pages **in parallel**, reducing generation time massively.

### 🛠️ Auto-Healing & E2E Testing
* **Technology:** `subprocess`, `Playwright` (Testing)
* **Function:** Once the code is generated, the system boots up the new project on port `5001`. It runs automated browser clicks (E2E testing) to verify UI elements. If it finds an error, it sends crash logs back to Gemini, which rewrites the broken file and restarts the server automatically (Self-healing).

### 💻 Main Dashboard & WebSocket UI
* **Technology:** `FastAPI`, `Uvicorn`, `WebSockets`, Vanilla `HTML/TailwindCSS`
* **Function:** The beautiful, modern glassmorphic UI you see when you start the project. As the Whisper model transcribes text, or as the AI writes code, the updates are pushed instantly to the browser using WebSockets.

---

## 3. Complete Step-by-Step Workflow (How it Works)

**1. Meeting Initiation**
- The user provides a Google Meet link on the dashboard and clicks "Join Call".
- The `BrowserMeetingAgent` launches a Playwright session and joins the meeting.

**2. Real-Time Audio Capture**
- Once joined, the `SystemAudioAgent` connects to the Windows loopback interface to capture what participants are saying.
- Audio is chunked and sent to a queue.

**3. Transcription**
- The background `Whisper Worker` pulls from the queue and feeds the audio to the `small.en` local AI model.
- Whisper converts the raw audio into text and streams it to the UI.

**4. Intelligent Requirement Extraction**
- The `LiveTranscriptManager` holds the streaming text in a buffer.
- When a 15-second pause occurs, it triggers the extraction process.
- The AI dynamically parses the spoken words to extract structured JSON data (features, pages, project name).

**5. Autonomous Incremental Generation Pipeline**
- The `app/main.py` orchestrator monitors for new requirements.
- It scaffolds the project folder, generates the Backend (FastAPI + SQLite), seeds the database, and generates the Frontend (HTML/JS) in parallel.

**6. Live Deployment & Testing**
- The system spins up a background server on port `5001`.
- It runs E2E tests using Playwright. If errors occur, it fixes them automatically using Gemini.

**7. Dashboard Sync**
- Throughout the entire process, WebSockets broadcast the live transcript, the pipeline state, and the final live preview URL directly to the user's sleek dashboard.

---

## 4. Architecture & Folder Structure

- `app/`: Main FastAPI application, routers, database configuration, models, services, and Jinja2 UI templates.
  - `app/api/`: API routers (`auth_router.py`, `meeting_router.py`, `project_router.py`).
  - `app/database/`: Database engine, sessions, and safe dynamic schema migration engine (`database.py`).
  - `app/models/`: SQLAlchemy ORM definitions (`User`, `SessionRecord`, `MeetingSummary`).
  - `app/services/`: Core logic (`auth_service.py`, `meeting_service.py`, `meeting_browser_agent.py`, `meeting_state.py`, `ai/meeting_summary_service.py`).
  - `app/templates/`: Modern, responsive dashboard, login, and registration templates.
- `agents/`: Autonomous meeting agents (`autonomous_engine.py`, `requirement_agent.py`, etc.).
- `meeting_engine/`: Realtime pipeline (Audio Queue, Whisper Worker, Transcript Manager, System Audio).
- `generators/`: Code generation modules for backend and frontend.
- `data/browser_profiles/`: Isolated Playwright browser contexts keyed per user (`user_{user_id}`).
- `tests/`: Automated pytest test suite covering authentication, data isolation, Google OAuth, AI summarization, and meeting browser lifecycle.

---

## 5. Setup & Configuration

### Prerequisites
- Python 3.10+
- Chrome or Chromium installed (`playwright install chromium`)
- (Optional) Local Ollama instance running with `qwen2.5-coder:7b` or compatible model for offline AI summaries.

### Quick Start
1. **Clone & Environment Setup:**
   ```bash
   cp .env.example .env
   # Edit .env with your preferred database or OAuth credentials if desired.
   ```
2. **Activate Virtual Environment & Install Dependencies:**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   playwright install chromium
   ```
3. **Run Database Migrations (Automatic):**
   The application automatically verifies and performs non-destructive schema migrations upon startup.
4. **Start the Application:**
   ```bash
   python start.py
   # Or directly with Uvicorn:
   python -m uvicorn app.main:app --reload
   ```
5. **Open the Dashboard:**
   Visit `http://127.0.0.1:8000` in your web browser.

---

## 6. Running Automated Tests

Run the full automated test suite (all mocks included, no live Google account or external API keys needed):

```bash
python -m pytest tests/ -v
```

All 18 tests cover:
- Password hashing & JWT session security
- User registration, login, logout, and token revocation
- Multi-user data isolation across sessions and projects
- Google OAuth URL generation, status, and validation
- AI meeting summarization (local Ollama + NLP fallback)
- Playwright meeting browser lifecycle, crash recovery, and profile isolation