import base64
import bcrypt
from cryptography.fernet import Fernet
from app.config import settings


def _fernet() -> Fernet:
    key = settings.fernet_key
    if not key:
        raise RuntimeError("FERNET_KEY not configured")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_password(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_password(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def verify_pin(pin: str, pin_hash: str) -> bool:
    return bcrypt.checkpw(pin.encode(), pin_hash.encode())


def generate_fernet_key() -> str:
    return Fernet.generate_key().decode()
