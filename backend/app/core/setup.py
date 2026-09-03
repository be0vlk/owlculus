"""Persistent one-time token support for initial Owlculus setup."""

import hmac
import os
import secrets
import sys
import threading
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Iterator

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlmodel import Session, select

from app.database.models import User

_DEFAULT_SETUP_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "setup"
SETUP_DATA_DIR = Path(
    os.environ.get("OWLCULUS_SETUP_DATA_DIR", str(_DEFAULT_SETUP_DATA_DIR))
)
SETUP_TOKEN_FILE = SETUP_DATA_DIR / ".setup_token"
_SQLITE_FIRST_USER_LOCK = threading.Lock()
_POSTGRES_FIRST_USER_LOCK_ID = 719_225_404


def _write_private_temp_file(token: str, destination: Path) -> Path:
    """Write and sync a private temporary token file beside its destination."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    )
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as token_file:
            token_file.write(token)
            token_file.flush()
            os.fsync(token_file.fileno())
        return temporary
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _write_setup_token(token: str, destination: Path) -> None:
    """Atomically publish a token with owner-only permissions."""
    temporary = _write_private_temp_file(token, destination)
    try:
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def generate_setup_token() -> str:
    """Generate and persist a new setup token with 32 bytes of entropy."""
    token = secrets.token_urlsafe(32)
    _write_setup_token(token, SETUP_TOKEN_FILE)
    return token


def create_setup_token_once() -> tuple[str, bool]:
    """Atomically create one shared token or return the already-persisted token."""
    token = secrets.token_urlsafe(32)
    temporary = _write_private_temp_file(token, SETUP_TOKEN_FILE)
    try:
        try:
            os.link(temporary, SETUP_TOKEN_FILE)
        except FileExistsError:
            existing_token = get_setup_token()
            if existing_token is None:
                raise RuntimeError("The setup token file is empty")
            return existing_token, False
        return token, True
    finally:
        temporary.unlink(missing_ok=True)


def get_setup_token() -> str | None:
    """Read the pending setup token from shared persistent storage."""
    try:
        return SETUP_TOKEN_FILE.read_text().strip() or None
    except FileNotFoundError:
        return None


def validate_setup_token(token: str | None) -> bool:
    """Compare a submitted token with the persisted token in constant time."""
    current_token = get_setup_token()
    if current_token is None or token is None:
        return False
    return hmac.compare_digest(current_token, token)


def clear_setup_token() -> None:
    """Remove the pending setup token if one exists."""
    SETUP_TOKEN_FILE.unlink(missing_ok=True)


@contextmanager
def serialize_first_user_creation(session: Session) -> Iterator[None]:
    """Serialize the empty-table check and first-user insert for supported databases."""
    bind = session.get_bind()
    dialect_name = bind.dialect.name
    externally_managed_connection = isinstance(bind, Connection)

    if dialect_name == "sqlite" and not externally_managed_connection:
        session.rollback()

    lock = _SQLITE_FIRST_USER_LOCK if dialect_name == "sqlite" else nullcontext()
    with lock:
        if dialect_name == "sqlite" and not externally_managed_connection:
            session.execute(text("BEGIN IMMEDIATE"))
        elif dialect_name == "postgresql":
            session.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                {"lock_id": _POSTGRES_FIRST_USER_LOCK_ID},
            )

        try:
            yield
        except Exception:
            if not externally_managed_connection:
                session.rollback()
            raise


def is_setup_required(session: Session) -> bool:
    """Return whether the installation has no users yet."""
    return session.exec(select(User.id).limit(1)).first() is None


def check_and_generate_setup_token(session: Session) -> None:
    """Create and display the first-run token once for an empty installation."""
    if not is_setup_required(session):
        return

    token, created = create_setup_token_once()
    if not created:
        return

    print(
        "\n"
        "============================================================\n"
        "  SETUP TOKEN (use this to create your admin account):\n"
        "\n"
        f"  {token}\n"
        "\n"
        "  This token is required to complete initial setup.\n"
        "  Retrieve it with: docker compose logs backend\n"
        "============================================================\n",
        file=sys.stderr,
        flush=True,
    )
