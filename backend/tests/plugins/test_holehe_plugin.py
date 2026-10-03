"""Holehe plugin contract tests."""

from typing import cast

import pytest
from sqlmodel import Session

from app.plugins.base_plugin import PluginRun, ResultEvent
from app.plugins.holehe_plugin import HolehePlugin


async def registered(email, client, out):
    out.append({"exists": True, "emailrecovery": "a***@example.com"})


async def unregistered(email, client, out):
    out.append({"exists": False})


async def silent(email, client, out):
    pass


async def broken(email, client, out):
    raise TimeoutError


@pytest.mark.asyncio
async def test_only_registered_platforms_are_reported(monkeypatch):
    plugin = HolehePlugin()
    monkeypatch.setattr(
        plugin, "_platforms", lambda: [broken, silent, unregistered, registered]
    )
    ctx = PluginRun.for_test(
        session=cast(Session, None),
        user=cast(object, None),
        api_keys={},
        evidence=[],
        entities=[],
    )

    events = [event async for event in plugin.run({"email": " a@example.com "}, ctx)]

    assert events == [
        ResultEvent.data(
            {
                "platform": "registered",
                "email": "a@example.com",
                "exists": True,
                "partial_info": "a***@example.com",
                "ratelimited": False,
                "error": None,
                "domain": "registered",
            }
        )
    ]


def test_platforms_come_from_holehe_modules():
    platforms = HolehePlugin()._platforms()

    assert len(platforms) > 100
    assert all(p.__module__.startswith("holehe.modules.") for p in platforms)
