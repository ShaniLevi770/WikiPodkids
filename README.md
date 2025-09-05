<h1 align="center">WikiPodkids — Hebrew Kids’ Podcast Generator (AI)</h1>

<p align="center"><strong>Generate safe, funny Hebrew podcast episodes from any topic — prompt-driven, TTS-powered, and cloud-saved.</strong></p>

<p align="center">
  <a href="#"><img alt="Python" src="https://img.shields.io/badge/Python-3.x-informational"></a>
  <a href="#"><img alt="Streamlit" src="https://img.shields.io/badge/Streamlit-app-brightgreen"></a>
  <a href="#"><img alt="OpenAI" src="https://img.shields.io/badge/OpenAI-prompt--driven-blue"></a>
  <a href="#"><img alt="Google TTS" src="https://img.shields.io/badge/Google%20TTS-Hebrew-ff69b4"></a>
  <a href="#"><img alt="Supabase" src="https://img.shields.io/badge/Supabase-storage-success"></a>
  <a href="#"><img alt="TiDB" src="https://img.shields.io/badge/TiDB-MySQL%20compatible-orange"></a>
</p>

> [!IMPORTANT]
> **WikiPodkids** turns a Hebrew topic into a short, kid-safe podcast episode. It builds an **LLM prompt**, converts to speech with **Google Cloud TTS**, stores the MP3 in **Supabase**, and saves `{topic, duration, script_text, mp3_url}` in **TiDB**. Admin controls: delete episodes, shutdown/maintenance mode; Pushover alerts every N new generations.


### ✨ Features
- **Prompt-driven script generation (OpenAI)** — structured prompt from topic + cleaned Hebrew summary.
- **Kid-safe guardrails (in the prompt)** — avoids scary/sad themes; length control (minutes → target chars/tokens + buffer).
- **Text-to-Speech (Hebrew)** — Google Cloud TTS (single configured voice); chunked synthesis for clarity/vendor limits.
- **Persistent storage** — Supabase stores MP3 (public/signed URL); TiDB stores `{topic, duration, script_text, mp3_url, created_at, rating?}`.
- **Simple RTL UI** — Streamlit interface designed for Hebrew content.
- **Modular pipeline** — `wiki → generator (prompt) → tts → store (Supabase) → db (TiDB)`.
- **Admin & developer controls** — delete (`ADMIN_DELETE_TOKEN`), shutdown/maintenance (`ADMIN_SHUTDOWN_TOKEN`), Pushover alerts every N new generations (`PUSHOVER_EVERY_N`, `PUSHOVER_APP_TOKEN`, `PUSHOVER_USER_KEY`).


### 🛠 Technology Stack
- **Python 3** + **Streamlit** — UI and app orchestration (RTL-ready).
- **OpenAI** — prompt-driven script generation with kid-safe guardrails.
- **Google Cloud Text-to-Speech** — Hebrew TTS (fixed voice), chunked synthesis.
- **Supabase Storage** — MP3 files (public/signed URLs).
- **TiDB Cloud** — stores script text + MP3 URL (MySQL-compatible).
- **Pushover** (optional) — push notifications every N new generations.
- **pip** — dependencies via `requirements.txt` (curated) + `requirements.lock.txt` (exact).


### 📦 Folder Structure
```
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
```

### 🚀 Run Locally (Quickstart)

```bash
git clone https://github.com/<your-username>/WikiPodkids.git
cd WikiPodkids
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.lock.txt   # or: -r requirements.txt
# create .env from the template below and place your GCP key as credentials.json
streamlit run app.py
```


### 🔑 Environment Variables (.env)

```ini
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
GOOGLE_APPLICATION_CREDENTIALS=credentials.json
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_BUCKET=podcasts
TIDB_URL=mysql+pymysql://<user>:<password>@<host>:4000/<database>?ssl_verify_identity=true
# TIDB_SSL_CA=certs/isrgrootx1.pem
ADMIN_DELETE_TOKEN=...
ADMIN_SHUTDOWN_TOKEN=...
PUSHOVER_APP_TOKEN=...
PUSHOVER_USER_KEY=...
PUSHOVER_EVERY_N=10
```

### ▶️ Usage
- Enter a topic in Hebrew and select a duration (e.g., 5 minutes).
- Generate → app fetches a Hebrew summary, builds the prompt, calls OpenAI, synthesizes MP3 via Google TTS, uploads MP3 to Supabase, writes metadata to TiDB.
- Listen in the browser; optionally rate/save (shareable link from Supabase).
- Admin controls — delete episodes with `ADMIN_DELETE_TOKEN`; toggle shutdown/maintenance with `ADMIN_SHUTDOWN_TOKEN`; Pushover alerts on every Nth new generation (`PUSHOVER_EVERY_N`).

### 🗄️ Example TiDB Table

```sql
CREATE TABLE episodes (
  id           VARCHAR(36) PRIMARY KEY,
  topic        VARCHAR(255) NOT NULL,
  duration_min DECIMAL(3,1) NOT NULL,
  script_text  MEDIUMTEXT NOT NULL,
  mp3_url      TEXT NOT NULL,
  rating       TINYINT NULL,
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_episodes_topic      ON episodes (topic);
CREATE INDEX idx_episodes_created_at ON episodes (created_at);
```

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
