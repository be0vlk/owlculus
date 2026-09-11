"""Provision a restricted login while preserving existing database credentials."""

from contextlib import closing

from psycopg2 import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


def provision_runtime_role(engine: Engine, username: str, password: str) -> None:
    """Grant application DML for existing and future migration-owned objects."""
    if not username or not password or username == engine.url.username:
        raise ValueError("Set distinct bootstrap and runtime database credentials")
    connection = engine.raw_connection()
    try:
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                "SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls "
                "FROM pg_roles WHERE rolname = %s",
                (username,),
            )
            role = cursor.fetchone()
            if role is not None:
                cursor.execute(
                    "SELECT 1 FROM pg_auth_members WHERE member = "
                    "(SELECT oid FROM pg_roles WHERE rolname = %s)",
                    (username,),
                )
                if any(role) or cursor.fetchone():
                    raise ValueError(
                        "Runtime role must have no elevated attributes or role memberships"
                    )
                cursor.execute(
                    "SELECT 1 FROM pg_class WHERE relowner = "
                    "(SELECT oid FROM pg_roles WHERE rolname = %s) "
                    "UNION ALL SELECT 1 FROM pg_namespace WHERE nspowner = "
                    "(SELECT oid FROM pg_roles WHERE rolname = %s) "
                    "UNION ALL SELECT 1 FROM pg_database WHERE datdba = "
                    "(SELECT oid FROM pg_roles WHERE rolname = %s)",
                    (username, username, username),
                )
                if cursor.fetchone():
                    raise ValueError(
                        "Runtime role must not own database objects; use a new runtime role"
                    )
                runtime_engine = create_engine(
                    engine.url.set(username=username, password=password),
                    hide_parameters=True,
                )
                try:
                    with runtime_engine.connect():
                        pass
                except SQLAlchemyError:
                    raise ValueError(
                        "Runtime database login failed; restore its existing password or follow the documented rotation procedure"
                    ) from None
                finally:
                    runtime_engine.dispose()
            else:
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS"
                    ).format(sql.Identifier(username)),
                    (password,),
                )
            cursor.execute("SELECT current_database(), current_user")
            identity = cursor.fetchone()
            assert identity is not None
            database, owner = identity
            identifiers = {
                "runtime": sql.Identifier(username),
                "database": sql.Identifier(database),
                "owner": sql.Identifier(owner),
            }
            for statement in (
                "REVOKE CREATE, TEMPORARY ON DATABASE {database} FROM PUBLIC",
                "REVOKE ALL ON DATABASE {database} FROM {runtime}",
                "GRANT CONNECT ON DATABASE {database} TO {runtime}",
                "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
                "REVOKE ALL ON SCHEMA public FROM {runtime}",
                "GRANT USAGE ON SCHEMA public TO {runtime}",
                "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {runtime}",
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {runtime}",
                "REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {runtime}",
                "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {runtime}",
                "ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {runtime}",
                "ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {runtime}",
            ):
                cursor.execute(sql.SQL(statement).format(**identifiers))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
