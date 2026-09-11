"""Bounded, opt-in Docker probes using the tracked production gateway config."""

import http.client
import json
import os
import socket
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.deployment import REPOSITORY_ROOT, load_compose_configuration


@pytest.mark.parametrize("topology", ("direct", "development", "reverse-proxy"))
def test_every_service_has_bounded_container_logs(topology):
    for service in load_compose_configuration(topology)["services"].values():
        assert service["logging"] == {
            "driver": "json-file",
            "options": {"max-size": "10m", "max-file": "3"},
        }


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.skipif(os.getenv("RUN_DOCKER_PROBES") != "1", reason="opt-in local Docker")
def test_gateway_bounds_declared_and_chunked_requests(
    tmp_path, client, admin_token, test_case
):
    folder = client.post(
        "/api/evidence/folders",
        json={"case_id": test_case.id, "title": "Documents"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert folder.status_code == 201
    received = []

    class Sink(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()

        def do_POST(self):
            total = 0
            chunks = []
            try:
                if self.headers.get("Transfer-Encoding") == "chunked":
                    while True:
                        size = int(self.rfile.readline().strip(), 16)
                        if not size:
                            break
                        chunks.append(self.rfile.read(size))
                        total += len(chunks[-1])
                        self.rfile.read(2)
                else:
                    chunks.append(self.rfile.read(int(self.headers["Content-Length"])))
                    total = len(chunks[-1])
                if self.headers.get("Content-Type", "").startswith(
                    "multipart/form-data"
                ):
                    response = client.post(
                        self.path,
                        content=b"".join(chunks),
                        headers={
                            key: value
                            for key, value in self.headers.items()
                            if key.lower() in ("content-type", "authorization")
                        },
                    )
                    self.send_response(response.status_code)
                    self.end_headers()
                    self.wfile.write(response.content)
                else:
                    self.send_response(200)
                    self.end_headers()
            except (ValueError, BrokenPipeError, ConnectionResetError):
                pass
            finally:
                received.append(total)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Sink)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = free_port()
    config = (
        (REPOSITORY_ROOT / "Caddyfile")
        .read_text()
        .replace("backend:8000", f"127.0.0.1:{server.server_port}")
        .replace("http://127.0.0.1:8080", f"http://127.0.0.1:{free_port()}")
    )
    path = tmp_path / "Caddyfile"
    path.write_text(config)
    name = f"owlculus-body-probe-{uuid.uuid4().hex[:10]}"
    try:
        docker(
            "run",
            "-d",
            "--pull",
            "never",
            "--name",
            name,
            "--network",
            "host",
            "-e",
            f"DOMAIN=http://127.0.0.1:{port}",
            "-e",
            "EVIDENCE_BODY_LIMIT=4096",
            "-e",
            "API_BODY_LIMIT=1024",
            "-v",
            f"{path}:/etc/caddy/Caddyfile:ro",
            "caddy:2-alpine",
        )
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                time.sleep(0.05)
        else:
            pytest.fail(docker("logs", name))

        for route, limit in (
            ("/api/evidence/", 4096),
            ("/api/evidence", 4096),
            ("/api/cases/", 1024),
        ):
            for authenticated in (False, True):
                for chunked in (False, True):
                    for size in (limit, limit + 1, limit * 8):
                        connection = http.client.HTTPConnection(
                            "127.0.0.1", port, timeout=5
                        )
                        headers = (
                            {"Authorization": f"Bearer {admin_token}"}
                            if authenticated
                            else {}
                        )
                        body = b"x" * size
                        if chunked:
                            body = iter(
                                [body[i : i + 256] for i in range(0, size, 256)]
                            )
                        connection.request(
                            "POST", route, body, headers, encode_chunked=chunked
                        )
                        response = connection.getresponse()
                        assert response.status == (200 if size == limit else 413), (
                            route,
                            authenticated,
                            chunked,
                            size,
                            response.status,
                        )
                        response.read()
                        connection.close()
        for count in (1, 2, 10):
            body = (
                b"".join(
                    f'--probe\r\nContent-Disposition: form-data; name="files"; filename="file-{count}-{i}.txt"\r\nContent-Type: text/plain\r\n\r\nEvidence\r\n'.encode()
                    for i in range(count)
                )
                + b"--probe--\r\n"
            )
            for authenticated in (False, True):
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                headers = {"Content-Type": "multipart/form-data; boundary=probe"}
                if authenticated:
                    headers["Authorization"] = f"Bearer {admin_token}"
                connection.request(
                    "POST",
                    f"/api/evidence/?title=batch&case_id={test_case.id}&category=Other",
                    iter([body]),
                    headers,
                    encode_chunked=True,
                )
                response = connection.getresponse()
                result = response.read()
                assert response.status == (201 if authenticated else 401), result
                if authenticated:
                    assert len(json.loads(result)["created"]) == count
                    assert json.loads(result)["failed"] == []
                connection.close()
        assert received
        assert max(received) <= 4096
    finally:
        docker("rm", "-f", name)
        server.shutdown()
        server.server_close()


@pytest.mark.skipif(os.getenv("RUN_DOCKER_PROBES") != "1", reason="opt-in local Docker")
def test_disposable_container_rotates_logs():
    name = f"owlculus-log-probe-{uuid.uuid4().hex[:10]}"
    try:
        docker(
            "run",
            "-d",
            "--pull",
            "never",
            "--name",
            name,
            "--log-driver",
            "json-file",
            "--log-opt",
            "max-size=4k",
            "--log-opt",
            "max-file=2",
            "--entrypoint",
            "sh",
            "caddy:2-alpine",
            "-c",
            'i=0; while [ "$i" -lt 500 ]; do echo "line-$i-abcdefghijklmnopqrstuvwxyz"; i=$((i+1)); done; echo ROTATION_COMPLETE',
        )
        docker("wait", name)
        logs = docker("logs", name)
        assert "ROTATION_COMPLETE" in logs
        assert "line-0-" not in logs
        assert len(logs.encode()) < 8192
    finally:
        docker("rm", "-f", name)
