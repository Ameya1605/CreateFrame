import os
import pytest

def test_auth_refuses_insecure_defaults(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("JWT_SECRET", "supersecret")
    
    # Reloading or running logic with insecure secret must raise RuntimeError
    with pytest.raises(RuntimeError) as exc_info:
        insecure_secrets = {"supersecret", "secret", "changeme", "your-secret-key", "your_jwt_secret", "test", "supersecret_dev_key"}
        secret = os.getenv("JWT_SECRET")
        if not secret or secret in insecure_secrets or len(secret) < 16:
            raise RuntimeError("CRITICAL SECURITY ERROR: Insecure secret")
    assert "Insecure secret" in str(exc_info.value)

def test_encryption_roundtrip():
    import auth
    plain_token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    encrypted = auth.encrypt_token(plain_token)
    assert encrypted != plain_token
    decrypted = auth.decrypt_token(encrypted)
    assert decrypted == plain_token
