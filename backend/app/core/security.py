import base64
import os
import secrets
import time
from datetime import timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

import bcrypt
import filetype
import jwt
from cryptography.fernet import Fernet
from fastapi import HTTPException, UploadFile
from werkzeug.utils import secure_filename

from .config import settings
from .utils import get_utc_now


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


# JWT Authentication
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


def verify_access_token(token: str, credentials_exception) -> str:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY.get_secret_value(), algorithms=[ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except jwt.PyJWTError:
        raise credentials_exception


MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB in bytes

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/html",
    "image/jpeg",
    "image/png",
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
        raise HTTPException(status_code=400, detail="No file name provided")

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
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE / (1024 * 1024)}MB",
            )

    await file.seek(0)

    kind = filetype.guess(content)

    if kind and kind.mime in ALLOWED_MIME_TYPES:
        return

    # If filetype couldn't detect the type or it's not in allowed types,
    # check if it might be a text file (including HTML)
    if file.content_type in ["text/plain", "text/html"]:
        try:
            content.decode("utf-8")
            # If we got here, it's valid UTF-8 text
            return
        except UnicodeDecodeError:
            pass

    raise HTTPException(status_code=400, detail="File type not allowed")


def secure_filename_with_path(filename: str, base_path: Path) -> str:
    """
    Generate a secure filename and ensure it's safe within the given path.
    Uses werkzeug's secure_filename for basic sanitization.
    If the filename already exists, appends a counter.
    """
    safe_name = secure_filename(filename)
    if not safe_name:
        safe_name = "unnamed_file"
    abs_base = base_path.absolute().resolve()

    name, ext = os.path.splitext(safe_name)

    counter = 1
    final_name = safe_name
    while (abs_base / final_name).exists():
        final_name = f"{name}_{counter}{ext}"
        counter += 1

    # Create full path and verify it's within base_path
    full_path = (abs_base / final_name).resolve()
    if not str(full_path).startswith(str(abs_base)):
        raise HTTPException(status_code=400, detail="Invalid file path")

    return final_name


# API Key Encryption
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

    try:
        fernet = Fernet(_get_encryption_key())
        decrypted = fernet.decrypt(encrypted_key.encode())
        return decrypted.decode()
    except Exception:
        return ""


# Ephemeral Token Management for WebSocket Authentication
class EphemeralTokenManager:
    """Manages single-use ephemeral tokens for WebSocket connections"""

    def __init__(self, token_ttl: int = 30):
        """
        Initialize the token manager

        Args:
            token_ttl: Token time-to-live in seconds (default: 30)
        """
        self.token_ttl = token_ttl
        # Store tokens with their associated data and expiration
        # Format: {token: (user_id, execution_id, expiration_timestamp)}
        self._tokens: Dict[str, Tuple[int, int, float]] = {}

    def create_token(self, user_id: int, execution_id: int) -> str:
        """
        Create a single-use ephemeral token for WebSocket authentication

        Args:
            user_id: The authenticated user's ID
            execution_id: The hunt execution ID

        Returns:
            A secure random token string
        """
        # Generate a secure random token
        token = secrets.token_urlsafe(32)

        # Store token with expiration
        expiration = time.time() + self.token_ttl
        self._tokens[token] = (user_id, execution_id, expiration)

        # Clean up expired tokens periodically
        self._cleanup_expired_tokens()

        return token

    def validate_token(self, token: str, execution_id: int) -> Optional[int]:
        """
        Validate and consume a single-use token

        Args:
            token: The token to validate
            execution_id: The execution ID to match against

        Returns:
            The user_id if valid, None otherwise
        """
        if token not in self._tokens:
            return None

        user_id, stored_execution_id, expiration = self._tokens[token]

        # Check if token is expired
        if time.time() > expiration:
            del self._tokens[token]
            return None

        # Check if execution_id matches
        if execution_id != stored_execution_id:
            return None

        # Token is valid - consume it (single-use)
        del self._tokens[token]

        return user_id

    def _cleanup_expired_tokens(self):
        """Remove expired tokens from storage"""
        current_time = time.time()
        expired_tokens = [
            token for token, (_, _, exp) in self._tokens.items() if current_time > exp
        ]
        for token in expired_tokens:
            del self._tokens[token]


# Global ephemeral token manager instance
ephemeral_token_manager = EphemeralTokenManager()
