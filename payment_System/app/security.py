
import os
import hashlib
import secrets

from cryptography.fernet import Fernet
from typing import Optional
from dotenv import load_dotenv
# ---------------------------------------------------------------------
# Master encryption key for Daraja credentials at rest.
# MUST be set in your .env — generate once with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Never commit this key. Losing it means losing access to all stored
# merchant Daraja credentials (they'd need to re-enter them).
# ---------------------------------------------------------------------
load_dotenv()

try:
    _FERNET_KEY = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
except Exception as e:
    raise RuntimeError(
        "Invalid CREDENTIAL_ENCRYPTION_KEY "
    )
_fernet = Fernet(_FERNET_KEY.encode())

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