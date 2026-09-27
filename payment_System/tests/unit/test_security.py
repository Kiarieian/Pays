"""Unit tests for security module."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.security import (
    generate_api_key,
    hash_api_key,
    verify_api_key,
    encrypt_value,
    decrypt_value,
)


class TestAPIKeys:
    def test_generate_api_key_returns_tuple(self):
        raw, prefix, key_hash = generate_api_key()
        assert isinstance(raw, str)
        assert isinstance(prefix, str)
        assert isinstance(key_hash, str)

    def test_api_key_prefix_is_12_chars(self):
        raw, prefix, _ = generate_api_key()
        assert len(prefix) == 12
        assert raw[:12] == prefix

    def test_api_key_starts_with_sk_live(self):
        raw, _, _ = generate_api_key()
        assert raw.startswith("sk_live_")

    def test_hash_is_deterministic(self):
        key = "sk_live_testkey123"
        h1 = hash_api_key(key)
        h2 = hash_api_key(key)
        assert h1 == h2

    def test_verify_correct_key(self):
        raw, _, key_hash = generate_api_key()
        assert verify_api_key(raw, key_hash) is True

    def test_verify_wrong_key(self):
        raw, _, key_hash = generate_api_key()
        wrong_raw = raw + "x"
        assert verify_api_key(wrong_raw, key_hash) is False

    def test_verify_different_keys_dont_match(self):
        _, _, hash1 = generate_api_key()
        raw2, _, _ = generate_api_key()
        assert verify_api_key(raw2, hash1) is False


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "my_secret_consumer_key"
        encrypted = encrypt_value(plaintext)
        assert encrypted is not None
        assert isinstance(encrypted, bytes)
        decrypted = decrypt_value(encrypted)
        assert decrypted == plaintext

    def test_encrypt_none_returns_none(self):
        assert encrypt_value(None) is None

    def test_decrypt_none_returns_none(self):
        assert decrypt_value(None) is None

    def test_different_encryptions_produce_different_ciphertext(self):
        plaintext = "same_value"
        e1 = encrypt_value(plaintext)
        e2 = encrypt_value(plaintext)
        # Fernet uses random IV, so ciphertexts differ
        assert e1 != e2
        # But both decrypt to same value
        assert decrypt_value(e1) == decrypt_value(e2)
