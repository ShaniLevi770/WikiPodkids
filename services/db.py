# services/db.py
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv, find_dotenv

# load .env
load_dotenv(find_dotenv(usecwd=True), override=True)

# one-line connection string, e.g.
# DATABASE_URL=mysql+pymysql://USER:PASS@HOST:4000/DB?ssl_ca=certs/ca.pem
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise RuntimeError("DATABASE_URL is missing in .env")

# create a global engine object for other modules to import
engine = create_engine(DB_URL, pool_pre_ping=True, pool_recycle=3600)

# optional quick test
def ping():
    with engine.connect() as conn:
        return conn.execute(text("SELECT 1")).scalar()
