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
            guidance = (
                f"Set {name} in .env to a production secret. "
                "For a new secret, run: openssl rand -hex 32. "
                "Existing installs must preserve SECRET_KEY and POSTGRES_PASSWORD; "
                "restore their original values instead of generating replacements."
            )
            if name == "RUNTIME_POSTGRES_PASSWORD":
                guidance = (
                    "RUNTIME_POSTGRES_* configures the restricted database login "
                    "used by the app and workers; POSTGRES_* configures the database "
                    "owner used for initialization and migrations. "
                    "When upgrading an install without a runtime login, add "
                    "RUNTIME_POSTGRES_USER=owlculus_runtime (different from POSTGRES_USER) "
                    "and RUNTIME_POSTGRES_PASSWORD to .env; generate its password with: "
                    "openssl rand -hex 32. Setup creates the login on startup. "
                    "If that login already exists, restore its existing password. "
                    "Existing installs must preserve SECRET_KEY and POSTGRES_PASSWORD."
                )
            raise ValueError(
                f"{name} must be explicitly set to a non-placeholder production secret; "
                f"{guidance}"
            )
