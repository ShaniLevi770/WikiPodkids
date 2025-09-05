# services/config.py


import os, io, base64
import streamlit as st
from pathlib import Path
from openai import OpenAI
from dotenv import dotenv_values, load_dotenv, find_dotenv

def load_env_portable():
    b64 = st.secrets.get("DOTENV_B64")
    if b64:
        raw = base64.b64decode(b64).decode("utf-8")
        vals = dotenv_values(stream=io.StringIO(raw))
        for k, v in vals.items():
            if v is not None and k not in os.environ:
                os.environ[k] = v
        return
    path = find_dotenv(usecwd=True)
    if path:
        load_dotenv(path, override=False)

load_env_portable()





load_dotenv(override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GCP_CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY חסר בקובץ .env או בסביבה.")
if not Path(GCP_CREDENTIALS_PATH).exists():
    raise RuntimeError(f"לא נמצא קובץ Google credentials בנתיב: {GCP_CREDENTIALS_PATH}")

# Google TTS looks for this env var:
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GCP_CREDENTIALS_PATH

# OpenAI client/model
oai = OpenAI(api_key=OPENAI_API_KEY)
OPENAI_MODEL = "gpt-4o-mini"

# Hebrew pacing (≈1000 chars per minute is comfy)
# How many characters your TTS speaks per minute (set from your measurement)
CHARS_PER_MIN       = int(os.getenv("CHARS_PER_MIN", "660"))  # you measured ≈662

# Token budgeting (lets the model write enough without hard cutoffs)
AVG_CHARS_PER_TOKEN = float(os.getenv("AVG_CHARS_PER_TOKEN", "2.8"))  # more tokens
MAXTOK_BUFFER       = float(os.getenv("MAXTOK_BUFFER", "0.25"))       # +25% headroom
MIN_TOKENS_FLOOR    = int(os.getenv("MIN_TOKENS_FLOOR", "512"))
MIN_CHARS_FLOOR     = int(os.getenv("MIN_CHARS_FLOOR", "600"))


