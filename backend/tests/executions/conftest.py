"""Real isolated PostgreSQL/Redis and separately supervised process fixture."""

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.core.security import create_access_token, encrypt_api_key
from app.database.models import Case, CaseUserLink, Client, SystemConfiguration, User
from app.database.upgrade_executions import upgrade


def eventually(check, timeout=40):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except (OSError, httpx.HTTPError) as error:
            last = error
        time.sleep(0.1)
    raise AssertionError(f"Readiness deadline exceeded: {last}")


def free_port():
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return connection.getsockname()[1]


class ExecutionSystem:
    def __init__(self, root, env):
        self.root, self.env = root, env
        self.processes = []
        self.logs = []

    def start(self, *args):
        log = (self.root / f"process-{len(self.processes)}.log").open("w")
        self.logs.append(log)
        process = subprocess.Popen(
            [sys.executable, *args],
            cwd=self.root,
            env=self.env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.processes.append(process)
        return process

    def api(self):
        port = free_port()
        process = self.start("-m", "tests.executions.runtime", "api", str(port))
        client = httpx.Client(
            base_url=f"http://127.0.0.1:{port}",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=5,
        )
        eventually(lambda: client.get("/health/ready").status_code == 200)
        return process, client

    def worker(self):
        return self.start("-m", "tests.executions.runtime", "worker")

    def stop(self, process):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)

    def close(self):
        for process in reversed(self.processes):
            self.stop(process)
        for log in self.logs:
            log.close()


@pytest.fixture
def execution_system(tmp_path):
    if os.environ.get("RUN_EXECUTION_ACCEPTANCE") != "1":
        pytest.skip(
            "Set RUN_EXECUTION_ACCEPTANCE=1 to run isolated Docker PostgreSQL/Redis acceptance"
        )
    namespace = f"owlculus-execution-{uuid4().hex[:12]}"
    names = []
    system = None
    engine = None
    try:
        ports = []
        for suffix, image, port, extra in [
            (
                "db",
                "postgres:15-alpine",
                5432,
                ["-e", "POSTGRES_PASSWORD=acceptance", "-e", "POSTGRES_DB=acceptance"],
            ),
            ("redis", "redis:7-alpine", 6379, []),
        ]:
            name = f"{namespace}-{suffix}"
            names.append(name)
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-d",
                    "--name",
                    name,
                    "-p",
                    f"127.0.0.1::{port}",
                    *extra,
                    image,
                ],
                check=True,
                capture_output=True,
            )
            info = json.loads(subprocess.check_output(["docker", "inspect", name]))[0]
            ports.append(info["NetworkSettings"]["Ports"][f"{port}/tcp"][0]["HostPort"])
        from app.core.config import settings

        env = {
            **os.environ,
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "acceptance",
            "POSTGRES_DB": "acceptance",
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": ports[0],
            "SECRET_KEY": settings.SECRET_KEY.get_secret_value(),
            "REDIS_URL": f"redis://127.0.0.1:{ports[1]}/0",
            "PLUGIN_QUEUE": namespace,
            "CUSTOM_API_KEY": "",
            "EXECUTION_TEST_DIR": str(tmp_path),
            "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
            "OWLCULUS_LOG_FILE": str(tmp_path / "api.log"),
        }
        engine = create_engine(
            f"postgresql://postgres:acceptance@127.0.0.1:{ports[0]}/acceptance"
        )

        def db_ready():
            return (
                subprocess.run(
                    [
                        "docker",
                        "exec",
                        names[0],
                        "pg_isready",
                        "-h",
                        "127.0.0.1",
                        "-U",
                        "postgres",
                    ],
                    capture_output=True,
                    check=False,
                ).returncode
                == 0
            )

        eventually(db_ready)
        SQLModel.metadata.create_all(engine)
        upgrade(engine)
        upgrade(engine)
        with Session(engine) as db:
            user = User(
                username="acceptance",
                email="acceptance@example.com",
                password_hash="unused",
                role="Investigator",
                is_active=True,
            )
            client = Client(name="Acceptance")
            db.add_all([user, client])
            db.flush()
            case = Case(case_number="ACCEPT-1", client_id=client.id)
            db.add(case)
            db.flush()
            db.add(CaseUserLink(case_id=case.id, user_id=user.id))
            db.add(
                SystemConfiguration(
                    api_keys={
                        "custom": {
                            "api_key": encrypt_api_key("acceptance-vault-secret"),
                            "is_active": True,
                        }
                    }
                )
            )
            db.commit()
            user_id, case_id = user.id, case.id
        system = ExecutionSystem(tmp_path, env)
        system.engine, system.user_id, system.case_id = engine, user_id, case_id
        system.token = create_access_token(data={"sub": "acceptance"})
        yield system
    finally:
        if system:
            system.close()
        if engine:
            engine.dispose()
        for name in names:
            subprocess.run(
                ["docker", "rm", "-f", name], capture_output=True, check=False
            )
