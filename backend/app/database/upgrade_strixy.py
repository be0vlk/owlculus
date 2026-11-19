"""Repeatable provisioning of the permanent Strixy Analyst identity, the
SystemConfiguration.strixy_settings column and StrixyRun.error_detail."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.database.models import User


def upgrade(database_engine: Engine) -> None:
    """Upgrade existing accounts without identifying humans by name or email."""
    with database_engine.begin() as connection:
        if database_engine.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(827104004)"))
        else:
            connection.execute(text("BEGIN IMMEDIATE"))
        columns = {column["name"] for column in inspect(connection).get_columns("user")}
        if "system_identity" not in columns:
            connection.execute(
                text('ALTER TABLE "user" ADD COLUMN system_identity VARCHAR')
            )
        config_columns = {
            column["name"]
            for column in inspect(connection).get_columns("systemconfiguration")
        }
        if "strixy_settings" not in config_columns:
            connection.execute(
                text("ALTER TABLE systemconfiguration ADD COLUMN strixy_settings JSON")
            )
        run_columns = {
            column["name"] for column in inspect(connection).get_columns("strixyrun")
        }
        if "error_detail" not in run_columns:
            connection.execute(
                text("ALTER TABLE strixyrun ADD COLUMN error_detail VARCHAR")
            )
        connection.execute(
            text(
                'CREATE UNIQUE INDEX IF NOT EXISTS user_system_identity_unique ON "user" (system_identity)'
            )
        )
        if database_engine.dialect.name == "postgresql":
            connection.execute(
                text("""DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = '"user"'::regclass AND conname = 'user_system_identity_policy') THEN
                    ALTER TABLE "user" ADD CONSTRAINT user_system_identity_policy CHECK (
                        system_identity IS NULL OR (system_identity = 'strixy'
                        AND role = 'Analyst' AND is_superadmin = false AND password_hash = '!')
                    );
                END IF;
            END $$""")
            )
        with Session(bind=connection) as session:
            if session.exec(
                select(User).where(User.system_identity == "strixy")
            ).first():
                return
            suffix = 0
            while True:
                username = "strixy" if suffix == 0 else f"strixy_ai_{suffix}"
                email = f"{username}@system.invalid"
                collision = session.exec(
                    select(User.id).where(
                        (User.username == username) | (User.email == email)
                    )
                ).first()
                if collision is None:
                    break
                suffix += 1
            session.add(
                User(
                    system_identity="strixy",
                    username=username,
                    email=email,
                    role="Analyst",
                    password_hash="!",
                    is_active=True,
                    is_superadmin=False,
                )
            )
            session.flush()
