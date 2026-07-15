from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 210_000
SALT_BYTES = 16


def validate_password_strength(password: str) -> None:
    if len(password) < 4:
        raise ValueError("password_too_short")
    if len(password) > 128:
        raise ValueError("password_too_long")


def hash_password(password: str) -> str:
    validate_password_strength(password)
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return "$".join(
        [
            "pbkdf2_sha256",
            str(PBKDF2_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    try:
        scheme, iterations_raw, salt_raw, digest_raw = stored_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = base64.b64decode(salt_raw.encode("ascii"), validate=True)
        expected = base64.b64decode(digest_raw.encode("ascii"), validate=True)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)
