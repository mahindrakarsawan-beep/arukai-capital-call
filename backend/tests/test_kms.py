"""TDD tests for GCP KMS key resolution — written BEFORE implementation."""
import base64
import os
import pytest
from unittest.mock import patch, MagicMock
import app.security as security


@pytest.fixture(autouse=True)
def reset_key_cache():
    """Reset the module-level key cache between tests."""
    security._encryption_key_cache = None
    security._cache_resolved = False
    yield
    security._encryption_key_cache = None
    security._cache_resolved = False


@pytest.fixture
def valid_key():
    return os.urandom(32)


def test_get_key_from_kms():
    key_bytes = os.urandom(32)
    mock_response = MagicMock()
    mock_response.plaintext = key_bytes

    with patch.dict(os.environ, {
        "KMS_KEY_RESOURCE_NAME": "projects/test/locations/eu/keyRings/ring/cryptoKeys/key",
        "KMS_WRAPPED_KEY": base64.b64encode(b"wrapped").decode(),
    }, clear=True):
        with patch("app.security.kms") as mock_kms:
            mock_client = MagicMock()
            mock_client.decrypt.return_value = mock_response
            mock_kms.KeyManagementServiceClient.return_value = mock_client

            result = security.get_encryption_key()
            assert result == key_bytes
            mock_client.decrypt.assert_called_once()


def test_get_key_from_env():
    key_bytes = os.urandom(32)
    with patch.dict(os.environ, {
        "FIELD_ENCRYPTION_KEY": base64.b64encode(key_bytes).decode(),
    }, clear=True):
        result = security.get_encryption_key()
        assert result == key_bytes


def test_get_key_none_when_no_config():
    with patch.dict(os.environ, {}, clear=True):
        result = security.get_encryption_key()
        assert result is None


def test_get_key_cached_after_first_call():
    key_bytes = os.urandom(32)
    with patch.dict(os.environ, {
        "FIELD_ENCRYPTION_KEY": base64.b64encode(key_bytes).decode(),
    }, clear=True):
        k1 = security.get_encryption_key()
        k2 = security.get_encryption_key()
        assert k1 is k2  # same object, not re-resolved


def test_get_key_kms_priority_over_env():
    kms_key = os.urandom(32)
    env_key = os.urandom(32)
    mock_response = MagicMock()
    mock_response.plaintext = kms_key

    with patch.dict(os.environ, {
        "KMS_KEY_RESOURCE_NAME": "projects/test/locations/eu/keyRings/ring/cryptoKeys/key",
        "KMS_WRAPPED_KEY": base64.b64encode(b"wrapped").decode(),
        "FIELD_ENCRYPTION_KEY": base64.b64encode(env_key).decode(),
    }, clear=True):
        with patch("app.security.kms") as mock_kms:
            mock_client = MagicMock()
            mock_client.decrypt.return_value = mock_response
            mock_kms.KeyManagementServiceClient.return_value = mock_client

            result = security.get_encryption_key()
            assert result == kms_key  # KMS wins over env


def test_encrypt_decrypt_with_resolved_key():
    key_bytes = os.urandom(32)
    with patch.dict(os.environ, {
        "FIELD_ENCRYPTION_KEY": base64.b64encode(key_bytes).decode(),
    }, clear=True):
        encrypted = security.encrypt_field("secret data")
        assert encrypted != "secret data"
        decrypted = security.decrypt_field(encrypted)
        assert decrypted == "secret data"


def test_encrypt_plaintext_when_no_key():
    with patch.dict(os.environ, {}, clear=True):
        result = security.encrypt_field("plaintext")
        assert result == "plaintext"
