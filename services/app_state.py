# services/app_state.py
import os, datetime as dt, requests
import streamlit as st
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

PUSHOVER_APP_TOKEN = os.getenv("PUSHOVER_APP_TOKEN")
PUSHOVER_USER_KEY  = os.getenv("PUSHOVER_USER_KEY")

def _ensure_row():
    try:
        sb.table("app_state").insert({"id":"main"}).execute()
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
    _ensure_row()
    return sb.table("app_state").select("*").eq("id","main").single().execute().data

def is_enabled() -> bool:
    return bool(get_state().get("app_enabled", True))

def set_enabled(enabled: bool):
    sb.table("app_state").update({"app_enabled": enabled}).eq("id","main").execute()

def increment_searches_and_maybe_notify(every: int = 10) -> int:
    _ensure_row()
    cur = sb.table("app_state").select("searches_total").eq("id","main").single().execute().data["searches_total"]
    new_total = cur + 1
    sb.table("app_state").update(
        {"searches_total": new_total, "last_notified_at": dt.datetime.utcnow().isoformat()}
    ).eq("id","main").execute()

    if every > 0 and new_total % every == 0:
        _send_push(f"🔔 App reached {new_total} searches.")
    return new_total
