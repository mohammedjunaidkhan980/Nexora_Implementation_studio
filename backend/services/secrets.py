import hashlib
import hmac
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


def get_jwt_secret_key() -> str:
    configured_secret = os.getenv("JWT_SECRET_KEY")
    if configured_secret:
        if len(configured_secret.encode("utf-8")) < 32:
            raise RuntimeError("JWT_SECRET_KEY must be at least 32 bytes long")
        return configured_secret

    config_root = Path(os.getenv("APPDATA", Path.home()))
    secret_path = config_root / "ai_implementation_studio" / "jwt_secret_key"
    secret_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with secret_path.open("x", encoding="utf-8") as secret_file:
            secret_file.write(secrets.token_urlsafe(48))
    except FileExistsError:
        pass

    secret = secret_path.read_text(encoding="utf-8").strip()
    if not secret:
        raise RuntimeError(f"JWT signing key file is empty: {secret_path}")
    return secret


def hash_organization_pin(organization_id: int, pin: str) -> str:
    secret = get_jwt_secret_key().encode("utf-8")
    message = f"organization-join-pin:{organization_id}:{pin}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def verify_organization_pin(
    organization_id: int, pin: str, expected_hash: str | None
) -> bool:
    if expected_hash is None:
        return False
    actual_hash = hash_organization_pin(organization_id, pin)
    return hmac.compare_digest(actual_hash, expected_hash)


def _fernet() -> Fernet:
    key = os.getenv("AGENT_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("AGENT_ENCRYPTION_KEY environment variable must be set")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise RuntimeError("AGENT_ENCRYPTION_KEY must be a valid Fernet key") from exc


def encrypt_api_key(api_key: str) -> str:
    return _fernet().encrypt(api_key.encode("utf-8")).decode("ascii")


def decrypt_api_key(encrypted_api_key: str) -> str:
    try:
        return _fernet().decrypt(encrypted_api_key.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeEncodeError, ValueError) as exc:
        raise RuntimeError("Stored agent API key could not be decrypted") from exc
