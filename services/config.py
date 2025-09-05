# services/config.py
import os, io, base64, json
from pathlib import Path

import streamlit as st
from dotenv import dotenv_values, load_dotenv, find_dotenv
from google.oauth2 import service_account
from openai import OpenAI

# ---- load .env (Cloud via DOTENV_B64, local via .env file) ----
def _load_env_portable():
    # Accessing st.secrets can raise if no secrets.toml exists locally — guard it.
    try:
        b64 = st.secrets.get("DOTENV_B64")
    except Exception:
        b64 = None

    if b64:
        raw = base64.b64decode(b64).decode("utf-8")
        vals = dotenv_values(stream=io.StringIO(raw))
        for k, v in vals.items():
            if v is not None and k not in os.environ:
                os.environ[k] = v
        return

    # local fallback
    path = find_dotenv(usecwd=True)
    if path:
        load_dotenv(path, override=False)

_load_env_portable()  # must run before any os.getenv below


# ---- OpenAI ----
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY חסר ב-secrets/.env")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
oai = OpenAI(api_key=OPENAI_API_KEY)


# ---- Google Cloud credentials ----
def build_gcp_credentials():
    """
    Prefer JSON-in-env (works on Streamlit Cloud),
    optionally support a secrets table, then local file path for dev.
    """
    # 1) JSON string in env (from DOTENV_B64/.env)
    js = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if js:
        try:
            return service_account.Credentials.from_service_account_info(json.loads(js))
        except Exception as e:
            raise RuntimeError("GCP_SERVICE_ACCOUNT_JSON קיים אבל אינו JSON תקין") from e

    # 2) (optional) secrets table if you ever used [gcp_service_account] in secrets.toml
    try:
        tbl = st.secrets.get("gcp_service_account")
    except Exception:
        tbl = None
    if tbl:
        return service_account.Credentials.from_service_account_info(dict(tbl))

    # 3) local dev fallback: path to json file
    path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if path and Path(path).exists():
        return service_account.Credentials.from_service_account_file(path)

    raise RuntimeError("GCP credentials לא נמצאו. הגדרו GCP_SERVICE_ACCOUNT_JSON או [gcp_service_account].")


# Lazy init so mere import doesn't explode if creds missing
_GCP_CREDS = None
def get_gcp_creds():
    global _GCP_CREDS
    if _GCP_CREDS is None:
        _GCP_CREDS = build_gcp_credentials()
    return _GCP_CREDS


# ---- App constants (keep yours) ----
CHARS_PER_MIN        = int(os.getenv("CHARS_PER_MIN", "660"))
AVG_CHARS_PER_TOKEN  = float(os.getenv("AVG_CHARS_PER_TOKEN", "2.8"))
MAXTOK_BUFFER        = float(os.getenv("MAXTOK_BUFFER", "0.25"))
MIN_TOKENS_FLOOR     = int(os.getenv("MIN_TOKENS_FLOOR", "512"))
MIN_CHARS_FLOOR      = int(os.getenv("MIN_CHARS_FLOOR", "600"))
