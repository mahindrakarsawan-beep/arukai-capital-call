"""TDD tests for field-level AES-256-GCM encryption — written BEFORE implementation."""
import base64
import os
import pytest
from unittest.mock import patch
from app.security import encrypt_field, decrypt_field


@pytest.fixture
def encryption_key():
    return os.urandom(32)


def test_encrypt_decrypt_roundtrip(encryption_key):
    value = "Meridian Capital Partners III, L.P."
    encrypted = encrypt_field(value, encryption_key)
    assert encrypted != value
    assert isinstance(encrypted, str)
    decrypted = decrypt_field(encrypted, encryption_key)
    assert decrypted == value


def test_encrypt_empty_string(encryption_key):
    encrypted = encrypt_field("", encryption_key)
    assert decrypt_field(encrypted, encryption_key) == ""


def test_encrypt_no_key_returns_plaintext():
    value = "USD 2,500,000"
    assert encrypt_field(value, None) == value


def test_decrypt_no_key_returns_plaintext():
    value = "USD 2,500,000"
    assert decrypt_field(value, None) == value


def test_encrypt_invalid_key_length():
    with pytest.raises(ValueError, match="32 bytes"):
        encrypt_field("test", b"shortkey")


def test_decrypt_invalid_key_length():
    with pytest.raises(ValueError, match="32 bytes"):
        decrypt_field("dGVzdA==", b"shortkey")


def test_decrypt_tampered_data(encryption_key):
    encrypted = encrypt_field("secret", encryption_key)
    tampered = encrypted[:-4] + "XXXX"
    with pytest.raises(ValueError):
        decrypt_field(tampered, encryption_key)


def test_decrypt_wrong_key(encryption_key):
    encrypted = encrypt_field("secret", encryption_key)
    wrong_key = os.urandom(32)
    with pytest.raises(ValueError):
        decrypt_field(encrypted, wrong_key)


def test_encrypt_non_string_raises():
    with pytest.raises(TypeError):
        encrypt_field(123, os.urandom(32))


def test_decrypt_non_string_raises():
    with pytest.raises(TypeError):
        decrypt_field(123, os.urandom(32))


def test_env_var_key_used_when_no_key_arg():
    key = os.urandom(32)
    key_b64 = base64.b64encode(key).decode()
    with patch.dict(os.environ, {"FIELD_ENCRYPTION_KEY": key_b64}):
        encrypted = encrypt_field("secret", None)
        assert encrypted != "secret"
        decrypted = decrypt_field(encrypted, None)
        assert decrypted == "secret"


def test_different_encryptions_produce_different_output(encryption_key):
    value = "same input"
    e1 = encrypt_field(value, encryption_key)
    e2 = encrypt_field(value, encryption_key)
    assert e1 != e2  # different nonces
    assert decrypt_field(e1, encryption_key) == value
    assert decrypt_field(e2, encryption_key) == value
