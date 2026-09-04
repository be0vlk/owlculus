"""Tests for the plugin HTTP-edge service."""

from collections.abc import AsyncGenerator
from contextlib import nullcontext
from typing import Any

import pytest
from sqlmodel import Session

from app.core.exceptions import AuthorizationException
from app.database.models import User
from app.plugins.base_plugin import BasePlugin, PluginRun, ResultEvent
from app.plugins.plugin_registry import PluginRegistry
from app.services.api_key_vault import StaticApiKeyVault
from app.services.plugin_service import PluginService


class MetadataPlugin(BasePlugin):
    def __init__(self):
        super().__init__(display_name="Metadata")
        self.parameters = {"query": {"type": "string", "required": True}}

    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        yield self.data({})


def service(session: Session) -> PluginService:
    return PluginService(
        session,
        StaticApiKeyVault({}),
        registry=PluginRegistry.from_classes([MetadataPlugin]),
        session_factory=lambda: nullcontext(session),
    )


@pytest.mark.asyncio
async def test_list_plugins_reads_registry_metadata(session: Session, test_admin: User):
    metadata = await service(session).list_plugins(current_user=test_admin)

    assert metadata["MetadataPlugin"]["display_name"] == "Metadata"
    assert "save_to_case" in metadata["MetadataPlugin"]["parameters"]


@pytest.mark.asyncio
async def test_analyst_cannot_list_plugins(session: Session, test_analyst: User):
    with pytest.raises(AuthorizationException):
        await service(session).list_plugins(current_user=test_analyst)


def test_open_run_uses_request_user_and_parameters(session: Session, test_user: User):
    with service(session).open_run(
        {"case_id": 42, "save_to_case": True}, current_user=test_user
    ) as run:
        assert run.session is session
        assert run.user is test_user
        assert run.case_id == 42
        assert run.save_to_case is True
