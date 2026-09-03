"""Deployment contracts for the same-origin Caddy gateway."""

import pytest

from tests.deployment import REPOSITORY_ROOT, load_compose_configuration

CADDYFILE = REPOSITORY_ROOT / "Caddyfile"
FRONTEND_DOCKERFILE = REPOSITORY_ROOT / "frontend/Dockerfile"


def _caddyfile() -> str:
    return CADDYFILE.read_text()


def test_gateway_image_builds_the_spa_into_caddy_and_validates_its_config():
    """Building the production image compiles the SPA and validates Caddy."""
    contents = FRONTEND_DOCKERFILE.read_text()

    assert "AS frontend-builder" in contents
    assert "FROM caddy:" in contents
    assert "COPY Caddyfile /etc/caddy/Caddyfile" in contents
    assert "COPY --from=frontend-builder" in contents
    assert "caddy validate --config /etc/caddy/Caddyfile" in contents


def test_caddy_routes_api_and_health_to_the_backend_before_spa_fallback():
    """Backend paths cannot fall through to the Vue entrypoint."""
    contents = _caddyfile()
    backend_matcher = "@backend path /api/* /health /health/*"
    backend_proxy = "reverse_proxy backend:8000"
    backend_import = "import backendProxy"
    spa_fallback = "try_files {path} /index.html"

    assert "{$DOMAIN::80} {" in contents
    assert "http://127.0.0.1:8080 {" in contents
    assert "(backendProxy) {" in contents
    assert backend_proxy in contents
    assert contents.index(backend_matcher) < contents.index(backend_import)
    assert contents.index(backend_import) < contents.index(spa_fallback)
    assert "uri strip_prefix" not in contents
    assert "health_uri /health/live" in contents


def test_caddy_forwards_the_browser_address_to_the_trusted_backend():
    """Security logging receives the browser address rather than the gateway."""
    contents = _caddyfile()

    assert "header_up X-Forwarded-For {remote_host}" in contents
    assert "header_up X-Real-IP {remote_host}" in contents


def test_caddy_applies_asset_caching_compression_and_security_headers():
    """Static responses have the production caching and security contract."""
    contents = _caddyfile()

    assert "@fingerprintedAssets path_regexp" in contents
    assert (
        'header @fingerprintedAssets Cache-Control '
        '"public, max-age=31536000, immutable"'
    ) in contents
    assert "header /index.html Cache-Control" not in contents
    assert "encode gzip zstd" in contents
    assert "-Server" in contents
    assert "handle_errors {" in contents
    assert "respond \"\" {http.error.status_code}" in contents
    assert "X-Content-Type-Options nosniff" in contents
    assert "X-Frame-Options DENY" in contents
    assert "Referrer-Policy strict-origin-when-cross-origin" in contents
    assert "Strict-Transport-Security" in contents
    assert "Permissions-Policy" in contents
    assert "Content-Security-Policy" in contents
    assert "connect-src 'self' ws://{http.request.host} wss://{http.request.host}" in contents


@pytest.mark.parametrize("topology", ("direct", "reverse-proxy"))
def test_production_exposes_only_the_caddy_gateway(topology):
    """The backend remains internal in every production invocation."""
    configuration = load_compose_configuration(topology)
    services = configuration["services"]

    assert services["backend"].get("ports", []) == []
    assert services["backend"]["expose"] == ["8000"]
    assert services["frontend"]["ports"] == [
        {
            "mode": "ingress",
            "protocol": "tcp",
            "published": "80",
            "target": 80,
        },
        {
            "mode": "ingress",
            "protocol": "tcp",
            "published": "443",
            "target": 443,
        },
    ]
    assert services["frontend"]["build"]["dockerfile"] == "frontend/Dockerfile"
    assert services["frontend"]["depends_on"]["backend"]["condition"] == "service_healthy"
    assert "http://127.0.0.1:8080/health/ready" in services["frontend"]["healthcheck"]["test"]


def test_default_and_explicit_domain_modes_use_the_same_gateway_stack():
    """DOMAIN alone switches Caddy from host-agnostic HTTP to a named site."""
    default = load_compose_configuration("direct")
    named = load_compose_configuration(
        "reverse-proxy",
        environment_overrides={"DOMAIN": "owlculus.example.com"},
    )

    assert default["services"]["frontend"]["environment"]["DOMAIN"] == ":80"
    assert (
        named["services"]["frontend"]["environment"]["DOMAIN"]
        == "owlculus.example.com"
    )
    assert default["services"].keys() == named["services"].keys()


def test_development_keeps_vite_and_direct_backend_access():
    """The Caddy production image does not replace the Vite development seam."""
    configuration = load_compose_configuration("development")

    assert configuration["services"]["frontend"]["build"]["dockerfile"] == "Dockerfile.dev"
    assert configuration["services"]["frontend"]["ports"][0]["published"] == "5173"
    assert configuration["services"]["backend"]["ports"][0]["published"] == "8000"


def test_setup_script_preserves_same_origin_gateway_defaults():
    """Generated deployment settings do not reintroduce host or port coupling."""
    contents = (REPOSITORY_ROOT / "setup.sh").read_text()

    assert 'DEFAULT_FRONTEND_PORT=80\n' in contents
    assert 'CADDY_DOMAIN=""' in contents
    assert "DOMAIN=$CADDY_DOMAIN" in contents
    assert "BACKEND_API_URL=" not in contents
    assert "FRONTEND_URL=$FRONTEND_URL" not in contents
    assert "VITE_API_BASE_URL=" not in contents
    assert "VITE_API_BASE_URL=$BACKEND_API_URL" not in contents
    assert 'curl -f -s "$FRONTEND_URL/health/ready"' in contents


def test_no_compose_file_references_nginx_or_an_operator_created_caddyfile():
    """All production artifacts are tracked and baked into the gateway image."""
    compose_files = list(REPOSITORY_ROOT.glob("docker-compose*.yml"))
    contents = "\n".join(path.read_text() for path in compose_files)

    assert "nginx" not in contents.lower()
    assert "./Caddyfile:" not in contents
    assert not (REPOSITORY_ROOT / "docker-compose.reverse-proxy.yml").exists()
    assert not (REPOSITORY_ROOT / "frontend/nginx.conf").exists()
    assert not (REPOSITORY_ROOT / "examples/Caddyfile").exists()
