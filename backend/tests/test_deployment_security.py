"""Production credential policy and merged development network contracts."""

import json
import os
import subprocess
import sys

import pytest

from app.core.deployment import PLACEHOLDERS, validate_deployment
from tests.deployment import REPOSITORY_ROOT, load_compose_configuration

SERVICES = (
    "backend",
    "plugin-worker",
    "hunt-worker",
    "execution-dispatcher",
    "db-init",
)


@pytest.mark.parametrize("invalid", ["", "  ", *sorted(PLACEHOLDERS)])
@pytest.mark.parametrize(
    "name", ["SECRET_KEY", "POSTGRES_PASSWORD", "RUNTIME_POSTGRES_PASSWORD"]
)
def test_production_rejects_invalid_secrets_without_disclosure(name, invalid):
    environment = {
        "SECRET_KEY": "explicit-auth-secret",
        "POSTGRES_PASSWORD": "explicit-bootstrap-password",
        "RUNTIME_POSTGRES_PASSWORD": "explicit-runtime-password",
        "POSTGRES_USER": "bootstrap",
        "RUNTIME_POSTGRES_USER": "runtime",
    }
    environment[name] = invalid
    with pytest.raises(ValueError, match=name) as error:
        validate_deployment(environment, bootstrap=True)
    if invalid.strip():
        assert invalid not in str(error.value)


def test_direct_production_and_setup_share_policy():
    for overrides, valid in [
        ({}, False),
        (
            {
                "SECRET_KEY": "development_key_not_secure",
                "POSTGRES_PASSWORD": "owlculus_secure_password",
            },
            False,
        ),
        (
            {
                "SECRET_KEY": "explicit-auth-secret",
                "POSTGRES_PASSWORD": "explicit-bootstrap-password",
                "RUNTIME_POSTGRES_PASSWORD": "explicit-runtime-password",
            },
            True,
        ),
    ]:
        config = load_compose_configuration("direct", environment_overrides=overrides)
        result = subprocess.run(
            [sys.executable, "scripts/validate-deployment.py"],
            input=json.dumps(config),
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert (result.returncode == 0) is valid
        for name in SERVICES:
            environment = config["services"][name]["environment"]
            if valid:
                validate_deployment(environment, bootstrap=name == "db-init")
            else:
                with pytest.raises(ValueError):
                    validate_deployment(environment, bootstrap=name == "db-init")
        for name in SERVICES[:-1]:
            environment = config["services"][name]["environment"]
            assert environment["POSTGRES_USER"] == "owlculus_runtime"
            assert "RUNTIME_POSTGRES_PASSWORD" not in environment
            assert environment["POSTGRES_PASSWORD"] != "explicit-bootstrap-password"
        assert "ports" not in config["services"]["postgres"]
        assert "ports" not in config["services"]["redis"]


def test_development_merge_and_explicit_remote_ports():
    for overrides, host, ports in [
        ({}, "127.0.0.1", [5432, 8000, 5173]),
        (
            {
                "DEV_BIND_HOST": "0.0.0.0",
                "DB_PORT": "15432",
                "BACKEND_PORT": "18000",
                "DEV_FRONTEND_PORT": "15173",
            },
            "0.0.0.0",
            [15432, 18000, 15173],
        ),
    ]:
        services = load_compose_configuration(
            "development", environment_overrides=overrides
        )["services"]
        for name in SERVICES:
            environment = services[name]["environment"]
            assert environment["OWLCULUS_ENV"] == "development"
            assert environment["SECRET_KEY"]
            assert environment["POSTGRES_PASSWORD"]
            validate_deployment(environment, bootstrap=name == "db-init")
        for name, port in zip(("postgres", "backend", "frontend"), ports):
            assert services[name]["ports"][0]["host_ip"] == host
            assert services[name]["ports"][0]["published"] == str(port)
        assert (
            services["frontend"]["environment"]["API_PROXY_TARGET"]
            == "http://backend:8000"
        )
        assert (
            services["backend"]["environment"]["FORWARDED_ALLOW_IPS"] == "172.30.0.254"
        )


@pytest.mark.parametrize(
    "secret", ["", "development_key_not_secure", "explicit-private-secret"]
)
def test_production_process_rejects_invalid_secrets_before_database_access(secret):
    environment = {
        **os.environ,
        "OWLCULUS_ENV": "production",
        "SECRET_KEY": secret,
        "POSTGRES_USER": "runtime",
        "POSTGRES_PASSWORD": "explicit-runtime-password",
        "POSTGRES_HOST": "unreachable.invalid",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "fixture",
    }
    environment.pop("RUNTIME_POSTGRES_USER", None)
    result = subprocess.run(
        [sys.executable, "-c", "import app.core.config"],
        cwd=REPOSITORY_ROOT / "backend",
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) is (secret == "explicit-private-secret")
    if result.returncode:
        assert "SECRET_KEY must be explicitly set" in result.stderr
    assert "explicit-runtime-password" not in result.stdout + result.stderr
