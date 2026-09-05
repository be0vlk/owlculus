"""Content identity shared by API and worker images, independent of Git metadata."""

from functools import lru_cache
from hashlib import sha256
from pathlib import Path


@lru_cache(maxsize=1)
def implementation_build() -> str:
    root = Path(__file__).resolve().parents[2]
    digest = sha256()
    for path in [*sorted((root / "app").rglob("*.py")), root / "uv.lock"]:
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()
