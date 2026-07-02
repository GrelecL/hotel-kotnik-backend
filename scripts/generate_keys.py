"""
Run once to generate required secret values for .env:
    python scripts/generate_keys.py
"""
import secrets
from cryptography.fernet import Fernet

print("# Paste these into your .env file:\n")
print(f"FERNET_KEY={Fernet.generate_key().decode()}")
print(f"DB_PASSWORD={secrets.token_urlsafe(24)}")
