"""Test-only startup shared by API, Celery workers, and provider children."""

from provider import install

install()
