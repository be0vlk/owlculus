"""Verify relationship normalization on a disposable PostgreSQL installation."""

from sqlalchemy import create_engine, text

from app.database.upgrade_case_relationships import upgrade


def test_relationship_upgrade_preserves_legacy_schema_and_valid_references(
    execution_system,
):
    engine = execution_system.engine
    # An isolated schema models an installation before either authorization ticket.
    # Its intentionally minimal account table proves cleanup needs no new claims columns.
    with engine.connect() as connection:
        connection.execute(text("CREATE SCHEMA relationship_upgrade_test"))
        connection.execute(text("SET search_path TO relationship_upgrade_test"))
        connection.execute(
            text(
                'CREATE TABLE "user" (id INTEGER PRIMARY KEY, role TEXT, is_active BOOLEAN)'
            )
        )
        connection.execute(
            text("CREATE TABLE caseuserlink (case_id INTEGER, user_id INTEGER)")
        )
        connection.execute(
            text(
                "CREATE TABLE evidence (id INTEGER PRIMARY KEY, case_id INTEGER, is_folder BOOLEAN, parent_folder_id INTEGER, content TEXT, folder_path TEXT)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE task (id INTEGER PRIMARY KEY, case_id INTEGER, assigned_to_id INTEGER, description TEXT)"
            )
        )
        connection.execute(
            text(
                """INSERT INTO "user" VALUES
            (1, 'Admin', TRUE), (2, 'Analyst', TRUE), (3, 'Investigator', FALSE), (4, 'Investigator', TRUE)"""
            )
        )
        connection.execute(text("INSERT INTO caseuserlink VALUES (1, 2), (1, 3)"))
        connection.execute(text("""INSERT INTO evidence VALUES
            (1, 1, TRUE, NULL, '', 'local'),
            (2, 2, TRUE, NULL, '', 'foreign'),
            (3, 1, FALSE, 2, '1/preserved.txt', 'original'),
            (4, 1, TRUE, 3, '', 'nonfolder-parent'),
            (5, 1, FALSE, 1, '1/valid.txt', 'local'),
            (6, 1, FALSE, 999, '1/missing.txt', 'original')"""))
        connection.execute(text("""INSERT INTO task VALUES
            (1, 1, 1, 'admin'), (2, 1, 2, 'analyst'),
            (3, 1, 3, 'inactive reader'), (4, 1, 4, 'outsider history'),
            (5, 1, 999, 'missing history')"""))
        connection.commit()
        scoped_engine = create_engine(
            engine.url,
            connect_args={"options": "-csearch_path=relationship_upgrade_test"},
        )
        try:
            for _ in range(2):
                upgrade(scoped_engine)
                assert connection.execute(
                    text("SELECT assigned_to_id FROM task ORDER BY id")
                ).scalars().all() == [1, 2, 3, None, None]
                assert connection.execute(
                    text("SELECT parent_folder_id FROM evidence ORDER BY id")
                ).scalars().all() == [None, None, None, None, 1, None]
                assert (
                    connection.execute(
                        text("SELECT content FROM evidence WHERE id=3")
                    ).scalar_one()
                    == "1/preserved.txt"
                )
                assert (
                    connection.execute(
                        text("SELECT description FROM task WHERE id=4")
                    ).scalar_one()
                    == "outsider history"
                )
                connection.commit()
        finally:
            scoped_engine.dispose()
            connection.execute(text("SET search_path TO public"))
            connection.execute(text("DROP SCHEMA relationship_upgrade_test CASCADE"))
            connection.commit()
