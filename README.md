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


### Environment Variables (.env)

```ini
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini

# Database (TiDB/MySQL)
MYSQL_HOST=...
MYSQL_PORT=4000
MYSQL_DB=...
MYSQL_USER=...
MYSQL_PASS=...

# Supabase
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_ANON_KEY=...
SUPABASE_BUCKET=podkids-audio

# Google Cloud TTS
# Option 1: inline JSON
GCP_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"...","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"...","token_uri":"https://oauth2.googleapis.com/token"}
# Option 2: path to local file (dev)
# GOOGLE_APPLICATION_CREDENTIALS=credentials.json

# Admin / alerts
ADMIN_TOKEN=...
ADMIN_DASH_SECRET=...
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
### Local dev & tests
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
python -m pytest -q
```
