"""Deployment contract tests for the trusted reverse-proxy boundary."""

import pytest

from app.core.config import settings
from tests.deployment import (
    REPOSITORY_ROOT,
    SUPPORTED_TOPOLOGIES,
    load_compose_configuration,
)


def test_backend_image_enables_proxy_headers_explicitly():
    """Both backend image targets make Uvicorn apply its proxy trust list."""
    contents = (REPOSITORY_ROOT / "backend/Dockerfile").read_text()

    development, production = contents.split("FROM runtime-base AS production")
    assert '"--proxy-headers"' in development
    assert 'CMD ["python", "-m", "app.serve"]' in production
    # Production's actual proxy/worker arguments are exercised in test_config.


def test_direct_backend_defaults_to_loopback_proxy_trust_only():
    """A directly published backend does not trust arbitrary network peers."""
    trusted_proxies = set(settings.FORWARDED_ALLOW_IPS.split(","))

    assert trusted_proxies == {"127.0.0.1", "::1"}


def test_caddy_topology_trusts_only_the_gateway_container():
    """The Caddy adapter gives its gateway the one address Uvicorn trusts."""
    configuration = load_compose_configuration("reverse-proxy")
    proxy_address = "172.29.0.254"

    backend_environment = configuration["services"]["backend"]["environment"]
    assert backend_environment["FORWARDED_ALLOW_IPS"] == proxy_address
    assert (
        configuration["services"]["frontend"]["networks"]["frontend-network"][
            "ipv4_address"
        ]
        == proxy_address
    )
    assert configuration["networks"]["frontend-network"]["ipam"]["config"] == [
        {"subnet": f"{proxy_address.rsplit('.', 1)[0]}.0/24"}
    ]


@pytest.mark.parametrize(
    "topology",
    SUPPORTED_TOPOLOGIES,
)
def test_compose_backends_share_persistent_rate_limit_storage(topology):
    """Every backend topology persists counters in its shared Redis service."""
    configuration = load_compose_configuration(topology)
    redis_service = configuration["services"]["redis"]
    backend = configuration["services"]["backend"]

    command = redis_service["command"]
    assert command[0] == "redis-server"
    assert command[command.index("--appendonly") + 1] == "yes"
    assert redis_service["volumes"] == [
        {
            "type": "volume",
            "source": ("redis_dev_data" if topology == "development" else "redis_data"),
            "target": "/data",
            "volume": {},
        }
    ]
    assert backend["environment"]["REDIS_URL"] == "redis://redis:6379/0"
    assert backend["depends_on"]["redis"]["condition"] == "service_healthy"
