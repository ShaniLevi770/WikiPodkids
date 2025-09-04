# quick_insert.py
from sqlalchemy import text
from services.db import engine
import uuid

with engine.begin() as conn:
    conn.execute(text("""
        INSERT INTO episodes
        (id, topic, minutes, lang, script, duration_sec, rating)
        VALUES (:id, :topic, :minutes, 'he', :script, :dur, 5)
    """), {
        "id": str(uuid.uuid4()),
        "topic": "TEST_TOPIC",
        "minutes": 5.0,
        "script": "hello world",
        "dur": 300
    })

with engine.connect() as conn:
    print(list(conn.execute(text("SELECT topic, minutes, rating FROM episodes ORDER BY created_at DESC LIMIT 3"))))
