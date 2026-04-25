"""
Get a Supabase access token for local API testing.
Usage: python scripts/get_token.py
"""
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    sys.exit("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set in .env")

email = input("Email: ")
password = input("Password: ")

resp = httpx.post(
    f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
    headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"},
    json={"email": email, "password": password},
)

data = resp.json()

if resp.status_code != 200:
    sys.exit(f"Auth failed: {data}")

token = data["access_token"]
print(f"\nAccess token (expires in {data.get('expires_in', '?')}s):\n")
print(token)
print("\nUse it as:\n  Authorization: Bearer <token>")
