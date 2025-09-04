# check_db.py
from services.db import ping
print("DB OK ✔️", ping())
