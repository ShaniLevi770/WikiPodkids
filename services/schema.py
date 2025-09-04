from sqlalchemy import text
from .db import engine

DDL = """
CREATE TABLE IF NOT EXISTS episodes (
  id              CHAR(36) PRIMARY KEY,
  topic           VARCHAR(255) NOT NULL,
  minutes         DECIMAL(3,1) NOT NULL,
  lang            VARCHAR(8) DEFAULT 'he',
  script          MEDIUMTEXT,
  duration_sec    INT,
  storage_key     TEXT,
  public_url      VARCHAR(512),
  rating          TINYINT,
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE INDEX IF NOT EXISTS idx_topic_minutes ON episodes(topic, minutes);
"""

def ensure_schema():
    with engine.begin() as conn:
        for stmt in [s.strip() for s in DDL.split(";") if s.strip()]:
            conn.execute(text(stmt))
