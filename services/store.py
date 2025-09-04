# services/store.py
from __future__ import annotations
import os
import uuid
import pathlib
import mimetypes
from typing import Optional, Tuple, List, Dict

from sqlalchemy import text
from .db import engine  # engine is defined in services/db.py

# ---------- Supabase (PUBLIC bucket) ----------
from supabase import create_client, Client

_SB: Client | None = None
def _sb() -> Client:
    """Lazy-init Supabase client from environment variables."""
    global _SB
    if _SB is None:
        url = os.getenv("SUPABASE_URL")
        # Server side: using Service Role is allowed for writes (bypass RLS), falls back to anon for read-only
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        if not url or not key:
            raise RuntimeError("Missing SUPABASE_URL or SUPABASE_*_KEY in .env")
        _SB = create_client(url, key)
    return _SB


def upload_mp3_to_supabase(local_path: str) -> Tuple[str, str]:
    """
    Upload MP3 to a **PUBLIC** Supabase bucket.
    Returns (public_url, storage_key). Public URLs do NOT expire.
    """
    bucket = os.getenv("SUPABASE_BUCKET", "podkids-audio")
    public_base = (os.getenv("SUPABASE_PUBLIC_BASE") or "").rstrip("/")
    if not public_base:
        raise RuntimeError("Missing SUPABASE_PUBLIC_BASE in .env")

    p = pathlib.Path(local_path)
    if not p.exists():
        raise FileNotFoundError(local_path)

    # Use only a UUID for key (avoid unsafe characters from topic)
    storage_key = f"audio/{uuid.uuid4().hex}.mp3"
    content_type = mimetypes.guess_type(p.name)[0] or "audio/mpeg"

    with p.open("rb") as f:
        _sb().storage.from_(bucket).upload(
            storage_key,
            f,
            file_options={
                "content-type": content_type,
                "x-upsert": "true",  # must be a string
            },
        )

    public_url = f"{public_base}/{bucket}/{storage_key}"
    return public_url, storage_key


def delete_supabase_object(storage_key: str) -> None:
    """Delete an object by its storage_key (path inside the bucket)."""
    if not storage_key:
        return
    bucket = os.getenv("SUPABASE_BUCKET", "podkids-audio")
    _sb().storage.from_(bucket).remove([storage_key])


# ---------- Core DB helpers ----------
def get_cached_podcast(topic: str, minutes: float) -> Optional[Dict]:
    """
    Return the latest 5-star episode for the exact (topic, minutes) pair, or None.
    """
    sql = text("""
        SELECT script, public_url, created_at
        FROM episodes
        WHERE topic = :topic AND minutes = :minutes AND rating = 5
        ORDER BY created_at DESC
        LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"topic": topic, "minutes": minutes}).fetchone()
        if not row:
            return None
        script, public_url, created_at = row
        return {
            "script": script,
            "public_url": public_url,
            "saved_at": str(created_at),
        }


def save_on_five_stars(
    topic: str,
    minutes: float,
    script: str,
    stars: int,
    public_url: Optional[str] = None,
    storage_key: Optional[str] = None,
) -> bool:
    """
    Insert a new episode only when stars == 5.
    """
    if stars != 5:
        return False

    sql = text("""
        INSERT INTO episodes
        (id, topic, minutes, lang, script, duration_sec, storage_key, public_url, rating)
        VALUES (:id, :topic, :minutes, 'he', :script, :duration_sec, :storage_key, :public_url, 5)
    """)
    with engine.begin() as conn:  # auto-commit
        conn.execute(sql, {
            "id": str(uuid.uuid4()),
            "topic": topic,
            "minutes": minutes,
            "script": script,
            "duration_sec": int(minutes * 60),
            "storage_key": storage_key,
            "public_url": public_url,
        })
    return True


def delete_episode_admin(topic: str, minutes: float, admin_token: str) -> tuple[bool, str]:
    """
    Admin delete: remove from DB and also delete the MP3 file from Supabase (if present).
    Requires ADMIN_TOKEN (from .env) to match the provided token.
    """
    required = os.getenv("ADMIN_TOKEN", "")
    if not required or admin_token != required:
        return False, "Unauthorized (invalid admin token)."

    # Fetch the latest row to find its storage_key
    sel = text("""
        SELECT id, storage_key FROM episodes
        WHERE topic = :topic AND minutes = :minutes AND rating = 5
        ORDER BY created_at DESC
        LIMIT 1
    """)
    with engine.begin() as conn:
        row = conn.execute(sel, {"topic": topic, "minutes": minutes}).fetchone()
        if not row:
            return False, "No matching record found to delete."

        ep_id, storage_key = row

        # Delete the file from Supabase (if exists)
        if storage_key:
            try:
                delete_supabase_object(storage_key)
            except Exception:
                # Continue with DB deletion even if removing the file failed
                pass

        # Delete from DB
        conn.execute(text("DELETE FROM episodes WHERE id = :id"), {"id": ep_id})

    return True, "Deleted successfully."


# ---------- Alphabetical listing (for sidebar) ----------
def list_saved_podcasts_alphabetical(
    limit: int = 20,
    offset: int = 0,
    collapse_by_minutes: bool = True,
    search: Optional[str] = None,
) -> List[Dict]:
    """
    List saved (rating=5) episodes alphabetically by topic (A→Z), then minutes.
    Supports optional search (ILIKE '%search%') and pagination.

    collapse_by_minutes=True  -> keep the latest row per (lower(topic), minutes)
    collapse_by_minutes=False -> keep the latest row per lower(topic) (minutes collapsed)
    """
    params: Dict[str, object] = {"limit": int(limit), "offset": int(offset)}
    search_clause = ""
    if search:
        search_clause = " AND topic ILIKE :search"
        params["search"] = f"%{search}%"

    if collapse_by_minutes:
        # One row per (topic, minutes) – latest by created_at
        sql = text(f"""
            WITH ranked AS (
                SELECT
                    id, topic, minutes, public_url, created_at, rating, script, storage_key,
                    ROW_NUMBER() OVER (
                        PARTITION BY lower(topic), minutes
                        ORDER BY created_at DESC
                    ) AS rn
                FROM episodes
                WHERE rating = 5{search_clause}
            )
            SELECT id, topic, minutes, public_url, created_at, rating, script, storage_key
            FROM ranked
            WHERE rn = 1
            ORDER BY lower(topic) ASC, minutes ASC
            LIMIT :limit OFFSET :offset
        """)
    else:
        # One row per topic – latest by created_at
        sql = text(f"""
            WITH ranked AS (
                SELECT
                    id, topic, minutes, public_url, created_at, rating, script, storage_key,
                    ROW_NUMBER() OVER (
                        PARTITION BY lower(topic)
                        ORDER BY created_at DESC
                    ) AS rn
                FROM episodes
                WHERE rating = 5{search_clause}
            )
            SELECT id, topic, minutes, public_url, created_at, rating, script, storage_key
            FROM ranked
            WHERE rn = 1
            ORDER BY lower(topic) ASC, minutes ASC
            LIMIT :limit OFFSET :offset
        """)

    with engine.connect() as conn:
        rows = conn.execute(sql, params).fetchall()

    out: List[Dict] = []
    for r in rows:
        ep_id, topic, minutes, public_url, created_at, rating, script, storage_key = r
        out.append({
            "id": ep_id,
            "topic": topic,
            "minutes": float(minutes) if minutes is not None else None,
            "public_url": public_url,
            "created_at": str(created_at) if created_at is not None else "",
            "stars": int(rating) if rating is not None else None,
            "script": script,
            "storage_key": storage_key,
        })
    return out
