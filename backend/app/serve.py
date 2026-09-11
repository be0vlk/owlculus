"""Production API launcher; development retains Uvicorn reload."""

import uvicorn

from app.core.config import settings


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        workers=settings.API_WORKERS,
        proxy_headers=True,
        forwarded_allow_ips=settings.FORWARDED_ALLOW_IPS,
    )


if __name__ == "__main__":
    main()
