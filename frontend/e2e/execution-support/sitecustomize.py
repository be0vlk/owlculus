"""Test-only startup shared by API, Celery workers, and provider children."""

from provider import install

install()

from strixy_provider import install as install_strixy

install_strixy()
