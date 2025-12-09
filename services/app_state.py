import os
import datetime as dt
import requests
import streamlit as st
from supabase import create_client, Client

PUSHOVER_APP_TOKEN = os.getenv("PUSHOVER_APP_TOKEN")
PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY")


def _client() -> Client | None:
    """Lazy-init Supabase client; return None if creds are missing so UI stays up."""
    url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", None)
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", None)
    if not (url and key):
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None


def _ensure_row(sb: Client):
    try:
        sb.table("app_state").insert({"id": "main"}).execute()
    except Exception:
        pass


def _send_push(msg: str):
    if not (PUSHOVER_APP_TOKEN and PUSHOVER_USER_KEY):
        return
    try:
        requests.post(
            "https://api.pushover.net/1/messages.json",
            data={"token": PUSHOVER_APP_TOKEN, "user": PUSHOVER_USER_KEY, "message": msg},
            timeout=5,
        )
    except Exception:
        pass


def get_state() -> dict:
    sb = _client()
    if sb is None:
        return {"app_enabled": True, "searches_total": 0}
    _ensure_row(sb)
    return sb.table("app_state").select("*").eq("id", "main").single().execute().data


def is_enabled() -> bool:
    return bool(get_state().get("app_enabled", True))


def set_enabled(enabled: bool):
    sb = _client()
    if sb is None:
        return
    sb.table("app_state").update({"app_enabled": enabled}).eq("id", "main").execute()


def increment_searches_and_maybe_notify(every: int = 10) -> int:
    sb = _client()
    if sb is None:
        return 0
    _ensure_row(sb)
    cur = sb.table("app_state").select("searches_total").eq("id", "main").single().execute().data["searches_total"]
    new_total = cur + 1
    sb.table("app_state").update(
        {"searches_total": new_total, "last_notified_at": dt.datetime.utcnow().isoformat()}
    ).eq("id", "main").execute()

    if every > 0 and new_total % every == 0:
        _send_push(f"App reached {new_total} searches.")
    return new_total
