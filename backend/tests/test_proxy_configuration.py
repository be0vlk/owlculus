"""Deployment contract tests for the trusted reverse-proxy boundary."""

from pathlib import Path

import pytest
import yaml
from app.core.config import settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("dockerfile", ["backend/Dockerfile", "backend/Dockerfile.dev"])
def test_backend_images_enable_proxy_headers_explicitly(dockerfile):
    """Container commands make Uvicorn apply its configured proxy trust list."""
    contents = (REPOSITORY_ROOT / dockerfile).read_text()

    assert '"--proxy-headers"' in contents


def test_direct_backend_defaults_to_loopback_proxy_trust_only():
    """A directly published backend does not trust arbitrary network peers."""
    trusted_proxies = set(settings.FORWARDED_ALLOW_IPS.split(","))

    assert trusted_proxies == {"127.0.0.1", "::1"}


@pytest.mark.parametrize(
    ("compose_file", "network_name", "proxy_address"),
    [
        ("docker-compose.caddy.yml", "frontend-network", "172.28.0.254"),
        ("docker-compose.reverse-proxy.yml", "owlculus-network", "172.29.0.254"),
    ],
)
def test_caddy_topologies_trust_only_the_gateway_container(
    compose_file, network_name, proxy_address
):
    """Each Caddy topology gives its gateway the one address Uvicorn trusts."""
    configuration = yaml.safe_load((REPOSITORY_ROOT / compose_file).read_text())

    backend_environment = configuration["services"]["backend"]["environment"]
    assert backend_environment["FORWARDED_ALLOW_IPS"].endswith(f":-{proxy_address}}}")
    assert (
        configuration["services"]["caddy"]["networks"][network_name]["ipv4_address"]
        == proxy_address
    )
    assert configuration["networks"][network_name]["ipam"]["config"] == [
        {"subnet": f"{proxy_address.rsplit('.', 1)[0]}.0/24"}
    ]


@pytest.mark.parametrize(
    "compose_file",
    [
        "docker-compose.yml",
        "docker-compose.dev.yml",
        "docker-compose.reverse-proxy.yml",
    ],
)
def test_compose_backends_share_persistent_rate_limit_storage(compose_file):
    """Every backend topology persists counters in its shared Redis service."""
    configuration = yaml.safe_load((REPOSITORY_ROOT / compose_file).read_text())
    redis_service = configuration["services"]["redis"]
    backend = configuration["services"]["backend"]

    assert redis_service["command"] == ["redis-server", "--appendonly", "yes"]
    assert redis_service["volumes"] == [
        (
            "redis_dev_data:/data"
            if compose_file == "docker-compose.dev.yml"
            else "redis_data:/data"
        )
    ]
    assert backend["environment"]["REDIS_URL"].endswith(":-redis://redis:6379/0}")
    assert backend["depends_on"]["redis"] == {"condition": "service_healthy"}
