"""Rehearse the released main schema cutover on disposable PostgreSQL/Redis."""

import hashlib
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import MetaData, select, text
from sqlmodel import Session

from app.core.security import encrypt_api_key, get_password_hash
from app.database.init_db import initialize_database
from app.database.models import Hunt, HuntExecution, HuntStep
from app.database.upgrade_executions import upgrade
from tests.executions.conftest import eventually
from tests.executions.test_execution_system import finished, submit
from tests.executions.test_hunt_execution_system import step, submit_hunt, terminal


def install_main_database(system):
    """Load every original table without deriving the baseline from new models."""
    schema = Path(__file__).parents[1] / "fixtures/main_3bc5348_schema.sql"
    metadata = MetaData()
    # The released schema stores TIMESTAMP WITHOUT TIME ZONE.
    stamp = datetime(2025, 12, 24, 12)  # noqa: DTZ001
    contents = b"Preserved investigation report\x00\r\n"
    report = system.root / "uploads/1/report.txt"
    report.parent.mkdir(parents=True)
    report.write_bytes(contents)
    with system.engine.begin() as connection:
        # This engine belongs exclusively to execution_system's disposable container.
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.exec_driver_sql(schema.read_text())
        metadata.reflect(connection)

        def insert(table_name, **values):
            table = metadata.tables[table_name]
            for column in ("created_at", "updated_at"):
                if column in table.c:
                    values.setdefault(column, stamp)
            return connection.execute(
                table.insert().values(**values)
            ).inserted_primary_key

        insert("client", name="Personal", email="client@example.com")
        for name, role in (("acceptance", "Admin"), ("analyst", "Analyst")):
            insert(
                "user",
                username=name,
                email=f"{name}@example.com",
                password_hash=get_password_hash("acceptance-password"),
                role=role,
                is_active=True,
                is_superadmin=name == "acceptance",
            )
        insert(
            "case",
            client_id=1,
            case_number="LEGACY-1",
            title="Legacy case",
            status="Open",
            notes="Keep notes",
        )
        insert(
            "case",
            client_id=1,
            case_number="LEGACY-2",
            title="Other case",
            status="Closed",
        )
        insert("caseuserlink", case_id=1, user_id=1, is_lead=True)
        insert("caseuserlink", case_id=1, user_id=2, is_lead=True)
        insert(
            "invite",
            token="historical-invite",
            role="Investigator",
            expires_at=stamp,
            used_at=stamp,
            created_by_id=1,
        )
        insert(
            "entity",
            case_id=1,
            entity_type="ip_address",
            data={"ip_address": "192.0.2.50"},
            created_by_id=1,
        )
        insert(
            "systemconfiguration",
            case_number_template="YYMM-NN",
            api_keys={
                "custom": {
                    "api_key": encrypt_api_key("acceptance-vault-secret"),
                    "is_active": True,
                }
            },
            evidence_folder_templates={"Other": ["Reports"]},
        )
        insert(
            "evidence",
            case_id=2,
            title="Other folder",
            evidence_type="folder",
            category="Other",
            content="",
            folder_path="original",
            is_folder=True,
            created_by_id=1,
        )
        insert(
            "evidence",
            case_id=1,
            title="Correlation Scan report",
            evidence_type="file",
            category="Other",
            content="1/report.txt",
            file_hash=hashlib.sha256(contents).hexdigest(),
            is_folder=False,
            parent_folder_id=1,
            created_by_id=1,
        )
        insert(
            "tasktemplate",
            name="legacy-template",
            display_name="Legacy template",
            description="Keep template",
            category="Other",
            is_active=True,
            created_by_id=1,
            definition_json={"fields": []},
        )
        insert(
            "task",
            case_id=2,
            template_id=1,
            title="Completed legacy task",
            description="Keep history",
            priority="Medium",
            status="Completed",
            assigned_to_id=2,
            assigned_by_id=1,
            completed_by_id=1,
            completed_at=stamp,
            custom_fields={"retained": True},
        )
        insert(
            "hunt",
            name="legacy-hunt",
            display_name="Legacy hunt",
            description="Keep definition",
            category="test",
            version="1.0.0",
            definition_json={"steps": []},
            is_active=True,
        )
        for status in ("completed", "running", "pending"):
            insert(
                "huntexecution",
                hunt_id=1,
                case_id=1,
                status=status,
                progress=100 if status == "completed" else 0,
                initial_parameters={"query": "owl"},
                context_data={"retained": True},
                created_by_id=1,
                completed_at=stamp if status == "completed" else None,
            )
        for retries in (3, 1):
            insert(
                "huntstep",
                execution_id=1,
                step_id="original",
                plugin_name="AcceptancePlugin",
                status="completed",
                parameters={"query": "owl"},
                output={"result_count": 1, "results": [{"retained": True}]},
                retry_count=retries,
                completed_at=stamp,
            )
        baseline = {
            table.name: [
                dict(row)
                for row in connection.execute(
                    select(table).order_by(*table.primary_key.columns)
                ).mappings()
            ]
            for table in metadata.sorted_tables
        }
    system.user_id, system.case_id = 1, 1
    return metadata, baseline, report, contents


def test_main_cutover_preserves_records_and_runs_new_work(execution_system):
    system = execution_system
    metadata, baseline, report, contents = install_main_database(system)
    # Exercise the actual deployment entry point with only the old schema present.
    for _ in range(2):
        subprocess.run(
            [sys.executable, "-m", "app.database.init_db"],
            cwd=system.root,
            env=system.env,
            check=True,
            capture_output=True,
            text=True,
        )
    with system.engine.connect() as connection:
        for name, old_rows in baseline.items():
            table = metadata.tables[name]
            rows = [
                dict(row)
                for row in connection.execute(
                    select(table).order_by(*table.primary_key.columns)
                ).mappings()
            ]
            expected = [dict(row) for row in old_rows]
            if name == "caseuserlink":
                expected[1]["is_lead"] = False
            elif name == "evidence":
                expected[1]["parent_folder_id"] = None
            elif name == "task":
                expected[0]["assigned_to_id"] = None
            elif name == "huntstep":
                expected[1]["step_id"] = "original__legacy_duplicate_2"
            elif name == "huntexecution":
                for row in expected[1:]:
                    row["status"] = "failed"
                    assert rows[row["id"] - 1]["completed_at"] is not None
                    row["completed_at"] = rows[row["id"] - 1]["completed_at"]
            assert rows == expected, name
        assert connection.execute(
            text("SELECT evidence_id, case_ids FROM correlationevidence")
        ).all() == [(2, None)]
        assert connection.execute(
            text(
                "SELECT error->>'code' FROM huntexecution WHERE id IN (2, 3) ORDER BY id"
            )
        ).scalars().all() == ["legacy_interrupted", "legacy_interrupted"]
    assert report.read_bytes() == contents

    _, client = system.api()
    try:
        assert client.get("/api/auth/setup-status").json() == {"setup_required": False}
        login = client.post(
            "/api/auth/login",
            data={"username": "acceptance", "password": "acceptance-password"},
        )
        assert login.status_code == 200, login.text
        client.headers["Authorization"] = "Bearer " + login.json()["access_token"]
        assert client.get("/api/users/me").json()["id"] == 1
        download = client.get("/api/evidence/2/download")
        assert download.status_code == 200, download.text
        assert download.content == contents
        history = client.get("/api/hunts/executions/1", params={"include_steps": True})
        assert history.status_code == 200, history.text
        assert len(history.json()["steps"]) == 2

        system.worker()
        system.start("-m", "tests.executions.runtime", "hunt-worker")
        system.start("-m", "app.executions.dispatcher")
        plugin = submit(client, system, mode="vault", save_to_case=True)
        assert eventually(lambda: finished(client, plugin))["status"] == "completed"
        hunt = submit_hunt(system, client, [step("new-step", save_to_case=True)])
        state = eventually(lambda: terminal(client, hunt))
        assert state["status"] == "completed", state
        assert state["steps"][0]["output"]["result_count"] == 1
        # Initialization is also safe after the upgraded application has written data.
        initialize_database(system.engine)
        assert client.get("/api/users/me").status_code == 200
        assert terminal(client, hunt) == state
    finally:
        client.close()


@pytest.mark.parametrize("legacy_column", [False, True])
def test_retry_compatibility_after_previous_upgrades(execution_system, legacy_column):
    system = execution_system
    if legacy_column:
        with system.engine.begin() as connection:
            # Versions 001-007 have already run, as on an earlier dev deployment.
            connection.execute(
                text("ALTER TABLE huntstep ADD COLUMN retry_count INTEGER NOT NULL")
            )
    for _ in range(2):
        upgrade(system.engine)
    with Session(system.engine) as db:
        hunt = Hunt(
            name="compatibility",
            display_name="Compatibility",
            description="Migration test",
            category="test",
            definition_json={"steps": []},
        )
        db.add(hunt)
        db.flush()
        execution = HuntExecution(
            hunt_id=hunt.id,
            case_id=system.case_id,
            created_by_id=system.user_id,
            initial_parameters={},
        )
        db.add(execution)
        db.flush()
        db.add(
            HuntStep(
                execution_id=execution.id,
                step_id="new",
                plugin_name="AcceptancePlugin",
                parameters={},
            )
        )
        db.commit()
    if legacy_column:
        with system.engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT retry_count FROM huntstep")
                ).scalar_one()
                == 0
            )


def test_main_duplicate_step_labels_do_not_collide(execution_system):
    system = execution_system
    install_main_database(system)
    with system.engine.begin() as connection:
        # These labels were legal in main and must not be overwritten by cleanup.
        for label in ("original__legacy_duplicate_2", "original__legacy_duplicate_2_"):
            connection.execute(
                text("""INSERT INTO huntstep
                    (execution_id, step_id, plugin_name, status, parameters, output, retry_count)
                    SELECT execution_id, :label, plugin_name, status, parameters, output, retry_count
                    FROM huntstep WHERE id = 1"""),
                {"label": label},
            )
    for _ in range(2):
        initialize_database(system.engine)
    with system.engine.connect() as connection:
        assert connection.execute(
            text("SELECT step_id FROM huntstep ORDER BY id")
        ).scalars().all() == [
            "original",
            "original__legacy_duplicate_2__",
            "original__legacy_duplicate_2",
            "original__legacy_duplicate_2_",
        ]
        assert connection.execute(
            text("SELECT retry_count FROM huntstep ORDER BY id")
        ).scalars().all() == [3, 1, 3, 3]
