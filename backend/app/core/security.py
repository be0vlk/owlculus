"""
Security utilities for password hashing, JWT tokens, file validation, and API key encryption.

This module provides comprehensive security functionality including password verification,
JWT token creation and validation, secure file upload handling, API key encryption/decryption,
and ephemeral token management for WebSocket authentication.
"""

import base64
import json
import os
import re
import secrets
import unicodedata
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import bcrypt
import filetype
import jwt
from cryptography.fernet import Fernet
from fastapi import UploadFile

from .config import settings
from .exceptions import ValidationException
from .utils import get_utc_now


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


ALGORITHM = "HS256"


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    now = get_utc_now()
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY.get_secret_value(), algorithm=ALGORITHM
    )
    return encoded_jwt


def _valid_session_claims(identity: object, version: object) -> bool:
    """Use one strict account/session contract for bearer and socket tokens."""
    if not isinstance(identity, str) or type(version) is not int or version < 0:
        return False
    try:
        return str(UUID(identity)) == identity
    except ValueError:
        return False


def verify_access_token(token: str, credentials_exception) -> tuple[str, int]:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[ALGORITHM],
            options={"require": ["sub", "session_version", "exp"]},
        )
        identity, version = payload["sub"], payload["session_version"]
        if not _valid_session_claims(identity, version):
            raise credentials_exception
        return identity, version
    except (jwt.PyJWTError, ValueError, TypeError):
        raise credentials_exception


MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB in bytes

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/html",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-ms-wmv",
    "audio/mpeg",
    "audio/wav",
    "audio/ogg",
}


async def validate_file_security(file: UploadFile) -> None:
    """
    Validate file security including size, type, and content.
    Uses filetype for proper file type detection, with special handling for text files.
    """
    if not file.filename:
        raise ValidationException("No file name provided")

    file_size = 0
    chunk_size = 1024 * 1024  # 1MB chunks
    content = b""
    await file.seek(0)

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        content += chunk
        file_size += len(chunk)
        if file_size > MAX_FILE_SIZE:
            await file.seek(0)
            raise ValidationException(
                f"File too large. Maximum size is {MAX_FILE_SIZE / (1024 * 1024):g} MiB"
            )

    await file.seek(0)

    kind = filetype.guess(content)

    if kind and kind.mime in ALLOWED_MIME_TYPES:
        return

    # If filetype couldn't detect the type or it's not in allowed types,
    # check if it might be a text file (including HTML)
    if file.content_type in ["text/plain", "text/html"] or (
        Path(file.filename).suffix.lower() in {".json", ".csv"}
        and file.content_type
        in {"application/json", "text/csv", "application/octet-stream"}
    ):
        try:
            content.decode("utf-8")
            return
        except UnicodeDecodeError:
            pass

    raise ValidationException("File type not allowed")


UNSAFE_FILENAME_CHARACTERS = re.compile(r"[^A-Za-z0-9_.-]")


def secure_filename_with_path(filename: str, base_path: Path) -> str:
    """
    Generate a secure filename and ensure it's safe within the given path.
    Reduces it to ASCII letters, digits, ``_``, ``.`` and ``-``.
    If the filename already exists, appends a counter.
    """
    ascii_name = (
        unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    )
    for separator in (os.sep, os.path.altsep):
        if separator:
            ascii_name = ascii_name.replace(separator, " ")
    safe_name = UNSAFE_FILENAME_CHARACTERS.sub("", "_".join(ascii_name.split()))
    safe_name = safe_name.strip("._")
    if not safe_name:
        safe_name = "unnamed_file"
    abs_base = base_path.absolute().resolve()

    name, ext = os.path.splitext(safe_name)

    counter = 1
    final_name = safe_name
    while (abs_base / final_name).exists():
        final_name = f"{name}_{counter}{ext}"
        counter += 1

    full_path = (abs_base / final_name).resolve()
    if not str(full_path).startswith(str(abs_base)):
        raise ValidationException("Invalid file path")

    return final_name


def _get_encryption_key() -> bytes:
    """Get or generate encryption key from secret."""
    secret = settings.SECRET_KEY.get_secret_value()
    key = base64.urlsafe_b64encode(secret.encode()[:32].ljust(32, b"0"))
    return key


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key for database storage."""
    if not api_key:
        return ""

    fernet = Fernet(_get_encryption_key())
    encrypted = fernet.encrypt(api_key.encode())
    return encrypted.decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key from database storage."""
    if not encrypted_key:
        return ""

    fernet = Fernet(_get_encryption_key())
    decrypted = fernet.decrypt(encrypted_key.encode())
    return decrypted.decode()


# Redis-backed, atomic single-use capabilities scoped to execution kind.
EPHEMERAL_TOKEN_TTL_SECONDS = 30


def create_ephemeral_token(
    user_id: int,
    execution_id: int,
    kind: str,
    auth_identity: str,
    session_version: int,
) -> str:
    from app.executions.events import redis_client

    token = secrets.token_urlsafe(32)
    with redis_client() as client:
        client.set(
            f"owlculus:tokens:{token}",
            json.dumps([user_id, kind, execution_id, auth_identity, session_version]),
            ex=EPHEMERAL_TOKEN_TTL_SECONDS,
            nx=True,
        )
    return token


def validate_ephemeral_token(
    token: str, execution_id: int, kind: str
) -> tuple[int, str, int] | None:
    from app.executions.events import redis_client

    with redis_client() as client:
        value = client.getdel(f"owlculus:tokens:{token}")
    if value is None:
        return None
    try:
        user_id, stored_kind, stored_id, identity, version = json.loads(value)
        if type(user_id) is not int or not _valid_session_claims(identity, version):
            return None
    except (ValueError, TypeError):
        return None
    return (
        (user_id, identity, version)
        if (stored_kind, stored_id) == (kind, execution_id)
        else None
    )
