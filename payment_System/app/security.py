import hashlib
import secrets

from cryptography.fernet import Fernet
from typing import Optional

from app.config import get_settings

settings = get_settings()

_fernet = Fernet(settings.security.credential_encryption_key.encode())


def encrypt_value(plaintext: Optional[str]) -> Optional[bytes]:
    """Encrypt a Daraja credential (consumer key, secret, passkey, etc.)."""
    if plaintext is None:
        return None
    return _fernet.encrypt(plaintext.encode())


def decrypt_value(ciphertext: Optional[bytes]) -> Optional[str]:
    """Decrypt a Daraja credential for use in an outgoing API call."""
    if ciphertext is None:
        return None
    return _fernet.decrypt(bytes(ciphertext)).decode()


# ---------------------------------------------------------------------
# API keys merchants use to call OUR gateway (not Daraja credentials).
# We store only a hash, like a password, since we never need to see
# the raw value again after issuing it once.
# ---------------------------------------------------------------------
API_KEY_PREFIX = "sk_live_"


def generate_api_key() -> tuple[str, str, str]:
    """
    Returns (raw_key, key_prefix_for_lookup, sha256_hash_to_store).
    raw_key is shown to the merchant ONCE at creation time and never stored.
    """
    raw_secret = secrets.token_urlsafe(32)
    raw_key = f"{API_KEY_PREFIX}{raw_secret}"
    key_prefix = raw_key[:12]  # stored in plaintext for fast DB lookup
    key_hash = hash_api_key(raw_key)
    return raw_key, key_prefix, key_hash


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    return secrets.compare_digest(hash_api_key(raw_key), stored_hash)


# ---------------------------------------------------------------------
# Password hashing for dashboard login.
# Uses SHA-256 with a random salt.  Not bcrypt (no C dependency),
# but adequate for this use case with rate-limited login attempts.
# ---------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash a password with a random salt. Returns 'salt:hash'."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{h}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a 'salt:hash' string."""
    try:
        salt, h = stored.split(":", 1)
    except ValueError:
        return False
    computed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return secrets.compare_digest(computed, h)


# ---------------------------------------------------------------------
# Session tokens for browser/dashboard access.
# Opaque tokens stored as SHA-256 hashes.
# ---------------------------------------------------------------------
def generate_session_token() -> tuple[str, str]:
    """Returns (raw_token, sha256_hash_to_store)."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
