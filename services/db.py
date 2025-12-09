import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv, find_dotenv

# Load .env locally (on Streamlit Cloud your config already injected env vars)
load_dotenv(find_dotenv(usecwd=True), override=False)

engine = None  # set below once we can build it safely


def _compose_tidb_url() -> str:
    """
    Build a mysql+pymysql DSN from parts:
    MYSQL_HOST, MYSQL_PORT (default 4000), MYSQL_DB, MYSQL_USER, MYSQL_PASS
    """
    host = os.getenv("MYSQL_HOST")
    port = os.getenv("MYSQL_PORT", "4000")
    db = os.getenv("MYSQL_DB")
    user = os.getenv("MYSQL_USER")
    pwd = os.getenv("MYSQL_PASS")
    if not all([host, db, user, pwd]):
        raise RuntimeError("Missing one of MYSQL_HOST / MYSQL_DB / MYSQL_USER / MYSQL_PASS in environment.")
    return f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}?charset=utf8mb4"


def _make_engine():
    url = _compose_tidb_url()
    ssl_args = {
        "ssl_disabled": False,
        "ssl_verify_cert": True,
        "ssl_verify_identity": True,
    }
    return create_engine(url, pool_pre_ping=True, future=True, connect_args={"ssl": ssl_args})


def _try_init_engine():
    """Attempt to create the engine and schema, but never crash the app if DB is misconfigured."""
    global engine
    try:
        engine = _make_engine()
        init_schema()
        print("DB connected")
    except Exception as e:
        engine = None
        print(f"DB unavailable: {e}. Running without database features.")


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


def ping():
    if engine is None:
        return None
    with engine.connect() as conn:
        return conn.execute(text("SELECT 1")).scalar()


_try_init_engine()

__all__ = ["engine", "init_schema", "ping"]
