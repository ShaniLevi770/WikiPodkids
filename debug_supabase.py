import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True), override=True)

k = os.getenv("SUPABASE_ANON_KEY") or ""
u = os.getenv("SUPABASE_URL") or ""
print("URL:", u)
print("Key length:", len(k))
print("Dots in key:", k.count("."))
print("Looks like JWT:", k.count(".") == 2)
