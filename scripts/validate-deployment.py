"""Validate rendered Compose credentials for setup without exposing their values."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.deployment import validate_deployment

try:
    services = json.load(sys.stdin)["services"]
    for name in (
        "db-init",
        "backend",
        "plugin-worker",
        "hunt-worker",
        "execution-dispatcher",
    ):
        validate_deployment(services[name]["environment"], bootstrap=name == "db-init")
except (ValueError, KeyError) as error:
    print(f"Deployment validation failed: {error}", file=sys.stderr)
    sys.exit(1)
