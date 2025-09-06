# services/db.py
import os
from pathlib import Path
from sqlalchemy import create_engine, text
from dotenv import load_dotenv, find_dotenv

# Load .env locally (on Streamlit Cloud your config already injected env vars)
load_dotenv(find_dotenv(usecwd=True), override=False)

def _compose_tidb_url() -> str:
    """
    Build a mysql+pymysql DSN from parts:
    MYSQL_HOST, MYSQL_PORT (default 4000), MYSQL_DB, MYSQL_USER, MYSQL_PASS
    """
    host = os.getenv("MYSQL_HOST")
    port = os.getenv("MYSQL_PORT", "4000")
    db   = os.getenv("MYSQL_DB")
    user = os.getenv("MYSQL_USER")
    pwd  = os.getenv("MYSQL_PASS")
    if not all([host, db, user, pwd]):
        raise RuntimeError(
            "Missing one of MYSQL_HOST / MYSQL_DB / MYSQL_USER / MYSQL_PASS in environment."
        )
    # Always set utf8mb4
    return f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}?charset=utf8mb4"

def _make_engine():
    # Compose TiDB DSN from parts (no DATABASE_URL)
    url = _compose_tidb_url()

    # TLS for TiDB Cloud - Fixed SSL configuration
    ca = os.getenv("MYSQL_SSL_CA")
    
    if ca:
        # If you have a specific CA file
        ssl_args = {"ca": ca}
    else:
        # For TiDB Cloud without specific CA - this is the fix!
        ssl_args = {
            "ssl_disabled": False,  # Enable SSL
            "ssl_verify_cert": False,  # Don't verify the certificate
            "ssl_verify_identity": False  # Don't verify identity
        }

    return create_engine(
        url,
        pool_pre_ping=True,
        future=True,
        connect_args={"ssl": ssl_args},
    )


engine = _make_engine()


def init_schema():
    """Create the 'episodes' table on TiDB/MySQL if it doesn't exist."""
    ddl = """
    CREATE TABLE IF NOT EXISTS episodes (
      id           VARCHAR(36) PRIMARY KEY,
      topic        TEXT NOT NULL,
      minutes      DOUBLE NOT NULL,
      lang         VARCHAR(8) DEFAULT 'he',
      script       LONGTEXT,
      duration_sec INT,
      storage_key  TEXT,
      public_url   TEXT,
      rating       INT,
      created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))

# Create the table at import (safe if it already exists)
init_schema()

def ping():
    with engine.connect() as conn:
        return conn.execute(text("SELECT 1")).scalar()

__all__ = ["engine", "init_schema", "ping"]
