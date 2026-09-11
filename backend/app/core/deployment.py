"""Validate deployment credentials without including secrets in diagnostics."""

from collections.abc import Mapping

PLACEHOLDERS = frozenset(
    {
        "development_key_not_secure",
        "dev_secret_key_change_in_production",
        "owlculus_secure_password",
        "owlculus_dev_password",
        "owlculus_dev_runtime_password",
        "change_me",
        "changeme",
        "your_secret_key_here",
        "your_secure_password_here",
    }
)


def validate_deployment(
    environment: Mapping[str, str], *, bootstrap: bool = False
) -> None:
    """Use the same policy in setup preflight and every production process."""
    if environment.get("OWLCULUS_ENV") == "development":
        return
    names = ["SECRET_KEY", "POSTGRES_PASSWORD"]
    if bootstrap:
        names.append("RUNTIME_POSTGRES_PASSWORD")
        if environment.get("POSTGRES_USER") == environment.get("RUNTIME_POSTGRES_USER"):
            raise ValueError("RUNTIME_POSTGRES_USER must differ from POSTGRES_USER")
    for name in names:
        value = environment.get(name, "").strip()
        if not value or value.lower() in PLACEHOLDERS:
            raise ValueError(
                f"{name} must be explicitly set to a non-placeholder production secret; "
                "see docs/deployment-security.md. Existing installs must preserve SECRET_KEY."
            )
