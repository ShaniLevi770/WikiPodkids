# services/store.py
from __future__ import annotations

import os
import uuid
import pathlib
import mimetypes
from typing import Optional, Tuple, List, Dict, Any

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
        # Server side in Streamlit: Service Role is fine for writes. Fall back to anon for read-only.
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        if not url or not key:
            raise RuntimeError("Missing SUPABASE_URL or SUPABASE_*_KEY in environment")
        _SB = create_client(url, key)
    return _SB


def upload_mp3_to_supabase(local_path: str) -> Tuple[str, str]:
    """
    Upload an MP3 to a **PUBLIC** Supabase bucket.
    Returns (public_url, storage_key). Public URL will work if the bucket is public.
    """
    bucket = os.getenv("SUPABASE_BUCKET", "podkids-audio")

    p = pathlib.Path(local_path)
    if not p.exists():
        raise FileNotFoundError(local_path)

    storage_key = f"audio/{uuid.uuid4().hex}.mp3"
    content_type = mimetypes.guess_type(p.name)[0] or "audio/mpeg"

    with p.open("rb") as f:
        # supabase-py v2 expects "contentType" and "upsert" strings in file_options
        _sb().storage.from_(bucket).upload(
            storage_key,
            f,
            file_options={
                "contentType": content_type,
                "upsert": "true",
            },
        )

    # Build a public URL (bucket must be public in Supabase dashboard)
    public_url = _sb().storage.from_(bucket).get_public_url(storage_key)
    return public_url, storage_key


def delete_supabase_object(storage_key: str) -> None:
    """Delete an object by its storage_key (path inside the bucket)."""
    if not storage_key:
        return
    bucket = os.getenv("SUPABASE_BUCKET", "podkids-audio")
    _sb().storage.from_(bucket).remove([storage_key])


# ---------- Optional: list files directly from Storage (for sidebar) ----------
def list_bucket_mp3s(
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    prefix: str = "",
) -> List[Dict[str, Any]]:
    """
    List MP3s from the public bucket (no DB required).
    Use this if you want the sidebar to show whatever is in Storage,
    even if the DB is empty on a fresh deploy.
    """
    bucket = os.getenv("SUPABASE_BUCKET", "podkids-audio")
    options: Dict[str, Any] = {"limit": page_size, "offset": (page - 1) * page_size}
    if search:
        options["search"] = search

    try:
        items = _sb().storage.from_(bucket).list(path=prefix, options=options)
        files = [i for i in items if i.get("name", "").lower().endswith(".mp3")]
        out: List[Dict[str, Any]] = []
        for f in files:
            name = f["name"]
            key = f"{prefix}/{name}" if prefix else name
            out.append(
                {
                    "name": name,
                    "public_url": _sb().storage.from_(bucket).get_public_url(key).replace(" ", "%20"),
                    "size": (f.get("metadata") or {}).get("size") or f.get("size"),
                    "updated_at": f.get("updated_at") or f.get("created_at"),
                    "storage_key": key,
                }
            )
        return out
    except Exception:
        # If listing fails (misconfig/bucket private), don't crash the UI
        return []


# ---------- Core DB helpers ----------
def get_cached_podcast(topic: str, minutes: float) -> Optional[Dict]:
    """
    Return the latest 5-star episode for the exact (topic, minutes) pair, or None.
    """
    sql = text(
        """
        SELECT script, public_url, created_at
        FROM episodes
        WHERE topic = :topic AND minutes = :minutes AND rating = 5
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    try:
        with engine.connect() as conn:
            row = conn.execute(sql, {"topic": topic, "minutes": minutes}).fetchone()
    except Exception:
        # Fresh deploys may not have a DB file/folder yet—avoid surfacing Errno 2
        return None

    if not row:
        return None
    script, public_url, created_at = row
    return {"script": script, "public_url": public_url, "saved_at": str(created_at)}


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

    sql = text(
        """
        INSERT INTO episodes
        (id, topic, minutes, lang, script, duration_sec, storage_key, public_url, rating)
        VALUES (:id, :topic, :minutes, 'he', :script, :duration_sec, :storage_key, :public_url, 5)
        """
    )
    try:
        with engine.begin() as conn:  # auto-commit
            conn.execute(
                sql,
                {
                    "id": str(uuid.uuid4()),
                    "topic": topic,
                    "minutes": minutes,
                    "script": script,
                    "duration_sec": int(minutes * 60),
                    "storage_key": storage_key,
                    "public_url": public_url,
                },
            )
    except Exception:
        # Don’t let DB write issues crash the app; you’ll still have the MP3 in Storage
        return False
    return True


def delete_episode_admin(topic: str, minutes: float, admin_token: str) -> tuple[bool, str]:
    """
    Admin delete: remove from DB and also delete the MP3 file from Supabase (if present).
    Requires ADMIN_TOKEN (from env) to match the provided token.
    """
    required = os.getenv("ADMIN_TOKEN", "")
    if not required or admin_token != required:
        return False, "Unauthorized (invalid admin token)."

    sel = text(
        """
        SELECT id, storage_key FROM episodes
        WHERE topic = :topic AND minutes = :minutes AND rating = 5
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    try:
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
                    pass

            # Delete from DB
            conn.execute(text("DELETE FROM episodes WHERE id = :id"), {"id": ep_id})
    except Exception as e:
        return False, f"Delete failed: {e}"

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
        sql = text(
            f"""
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
            """
        )
    else:
        sql = text(
            f"""
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
            """
        )

    try:
        with engine.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except Exception:
        # If the DB is not ready (fresh deploy, path missing), avoid Errno 2
        return []

    out: List[Dict] = []
    for r in rows:
        ep_id, topic, minutes, public_url, created_at, rating, script, storage_key = r
        out.append(
            {
                "id": ep_id,
                "topic": topic,
                "minutes": float(minutes) if minutes is not None else None,
                "public_url": public_url,
                "created_at": str(created_at) if created_at is not None else "",
                "stars": int(rating) if rating is not None else None,
                "script": script,
                "storage_key": storage_key,
            }
        )
    return out
