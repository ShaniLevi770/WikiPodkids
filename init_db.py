# init_db.py
from services.schema import ensure_schema

if __name__ == "__main__":
    ensure_schema()
    print("✅ Database schema ensured.")
