WikiPodkids — Hebrew Kids’ Podcast Generator (AI)

This web app turns a single Hebrew topic into a short, funny, kid-safe podcast episode. It fetches a clean Hebrew summary (e.g., from Wikipedia), builds an LLM prompt to generate an age-appropriate script, converts it to speech (Google Cloud TTS, fixed Hebrew voice), uploads the MP3 to Supabase, and records the script + MP3 URL in TiDB.

✨ Features

🎙 1) Prompt-driven script generation (OpenAI)
Structured prompt from topic + cleaned Hebrew summary produces a playful, factual script.

🛡 2) Kid-safe guardrails (in the prompt)
Avoids scary/sad themes and fear/disaster humor. Length control (minutes → target chars/tokens + buffer) for consistent runtime.

🔊 3) Text-to-Speech (Hebrew)
Google Cloud TTS (single configured voice). Chunking improves clarity and stays within vendor limits.

💾 4) Persistent storage

Supabase Storage: MP3 files (public/signed URL).

TiDB Cloud: {topic, duration, script_text, mp3_url, created_at, rating?} for history and queries.

↔️ 5) Simple RTL UI
Streamlit UI designed for Hebrew content (right-to-left).

🧩 6) Modular pipeline
wiki → generator (prompt) → tts → store (Supabase) → db (TiDB) — swap components without touching the UI.

🧑‍💻 7) Admin & developer controls

🗑 Token-gated delete — ADMIN_DELETE_TOKEN enables deleting saved episodes (removes MP3 in Supabase + its TiDB row).

⛔ Shutdown/Maintenance mode — ADMIN_SHUTDOWN_TOKEN locks the app (disables “Generate” + shows maintenance banner).

📣 Push alerts every N new generations — Pushover integration sends a notification on every 10th non-cached generation by default (PUSHOVER_EVERY_N, PUSHOVER_APP_TOKEN, PUSHOVER_USER_KEY).

### 🛠 Technology Stack
- Python 3 + Streamlit — UI and app orchestration (RTL-ready for Hebrew).
- OpenAI — prompt-driven script generation (kid-safe guardrails).
- Google Cloud Text-to-Speech — Hebrew TTS (single configured voice), chunked synthesis.
- Supabase Storage — stores MP3 files (public/signed URLs).
- TiDB Cloud (MySQL-compatible) — stores `{topic, duration, script_text, mp3_url, created_at, rating?}`.
- Pushover (optional) — push notifications every N new generations.
- Dependency management — `requirements.txt` (curated) + `requirements.lock.txt` (exact).


📦 Folder Structure
WikiPodkids/
├── app.py
├── services/
│   ├── config.py        # API clients, constants (model, chars/min, buffers)
│   ├── wiki.py          # Fetch & clean Hebrew summary (e.g., Wikipedia)
│   ├── generator.py     # Build LLM prompt + length budgeting + guardrails
│   ├── tts.py           # Chunk & synthesize via Google TTS; stitch MP3
│   ├── store.py         # Supabase upload/list/delete; signed/public URLs
│   ├── db.py            # TiDB writes/reads (script text + MP3 URL)
│   ├── schema.py        # Optional: table helpers
│   └── limits.py        # (roadmap) quotas & daily/total caps
├── requirements.txt
├── requirements.lock.txt
├── .gitignore
└── README.md

🚀 Run Locally (Quickstart)
git clone https://github.com/<your-username>/WikiPodkids.git
cd WikiPodkids
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.lock.txt   # or: -r requirements.txt
# create .env from the template below and place your GCP key as credentials.json
streamlit run app.py

🔑 Environment Variables (.env)
# OpenAI
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini

# Google TTS
GOOGLE_APPLICATION_CREDENTIALS=credentials.json

# Supabase (MP3 storage)
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_BUCKET=podcasts

# TiDB (SQLAlchemy URL; MySQL-compatible)
TIDB_URL=mysql+pymysql://<user>:<password>@<host>:4000/<database>?ssl_verify_identity=true
# Optional CA:
# TIDB_SSL_CA=certs/isrgrootx1.pem

# Admin / Dev
ADMIN_DELETE_TOKEN=...
ADMIN_SHUTDOWN_TOKEN=...
PUSHOVER_APP_TOKEN=...
PUSHOVER_USER_KEY=...
PUSHOVER_EVERY_N=10

### ▶️ Usage
- Enter a topic in Hebrew and select a duration (e.g., 5 minutes).
- Generate → app fetches a Hebrew summary, builds the prompt, calls OpenAI, synthesizes MP3 via Google TTS, uploads MP3 to Supabase, writes metadata to TiDB.
- Listen in the browser; optionally rate/save (shareable link from Supabase).
- Admin controls — delete episodes with `ADMIN_DELETE_TOKEN`; toggle shutdown/maintenance with `ADMIN_SHUTDOWN_TOKEN`; Pushover alerts on every Nth new generation (`PUSHOVER_EVERY_N`).


🗄 Example TiDB Table
CREATE TABLE episodes (
  id            VARCHAR(36) PRIMARY KEY,
  topic         VARCHAR(255) NOT NULL,
  duration_min  DECIMAL(3,1) NOT NULL,
  script_text   MEDIUMTEXT NOT NULL,
  mp3_url       TEXT NOT NULL,
  rating        TINYINT NULL,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_episodes_topic ON episodes (topic);
CREATE INDEX idx_episodes_created_at ON episodes (created_at);

### 🧪 Testing
- Unit — generator length budgeting (minutes → chars/tokens), wiki cleaner, TTS chunker utilities.
- Integration — end-to-end topic → MP3 with stubbed OpenAI/TTS to make CI deterministic.
- DB/Storage — Supabase upload/delete flow; TiDB insert/query/delete; URL integrity checks.
- Admin — token-gated delete behavior; shutdown/maintenance lock (UI disabled state).
- Alerts — notifier triggers on every Nth generation; back-off and error handling.


### 🧭 Roadmap
- Quotas — per-IP/per-user caps (daily/total) with “unlock” key and server-side counters.
- Cost guards — budget alerts and soft/hard limits for OpenAI/TTS usage.
- Voices — optional ElevenLabs or multi-voice selection behind a feature flag.
- Safety — lightweight moderation/fact checks prior to TTS; stricter prompt templates.
- Ops — `.env.example`, CI pipeline with tests, basic telemetry/metrics dashboards.
git status