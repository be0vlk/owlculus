"""
Holehe plugin for checking email account registrations across platforms
"""

import asyncio
import importlib
import pkgutil
from collections.abc import AsyncGenerator, Callable
from typing import Any

import holehe.modules
import httpx
from holehe.core import get_functions

from .base_plugin import BasePlugin, PluginRun, ResultEvent


class HolehePlugin(BasePlugin):
    """Plugin to check if email addresses are registered on various platforms using Holehe"""

    def __init__(self):
        super().__init__(display_name="Holehe")
        self.description = "Check if email addresses are registered on 120+ platforms using account recovery verification"
        self.category = "Person"
        self.evidence_category = "Social Media"
        self.parameters = {
            "email": {
                "type": "string",
                "description": "Email address to check for account registrations",
                "required": True,
            },
            "timeout": {
                "type": "float",
                "description": "Request timeout per platform in seconds",
                "default": 10.0,
                "required": False,
            },
        }

    def _platforms(self) -> list[Callable]:
        """Holehe's platform checks, skipping any module that fails to import."""
        modules = {}
        for _, name, _ in pkgutil.walk_packages(
            holehe.modules.__path__, "holehe.modules."
        ):
            try:
                modules[name] = importlib.import_module(name)
            except ImportError:
                continue
        return get_functions(modules)

    async def _check_single_platform(
        self, platform_func: Callable, email: str, client: httpx.AsyncClient
    ) -> dict[str, Any] | None:
        """Check one platform; failures and empty responses are dropped."""
        out: list[dict[str, Any]] = []
        try:
            await platform_func(email, client, out)
        except Exception:
            return None
        if not out:
            return None
        result = out[0]
        platform_name = platform_func.__name__
        return {
            "platform": platform_name,
            "email": email,
            "exists": result.get("exists", False),
            "partial_info": result.get("emailrecovery") or result.get("phoneNumber"),
            "ratelimited": result.get("ratelimit", False),
            "error": result.get("error"),
            "domain": result.get("domain", platform_name),
        }

    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        if not params or "email" not in params:
            yield self.error("Email parameter is required")
            return
        email = params["email"].strip()
        timeout = params.get("timeout", 10.0)
        if not email:
            yield self.error("Email address cannot be empty")
            return
        async with httpx.AsyncClient(timeout=timeout) as client:
            for platform_func in self._platforms():
                result = await self._check_single_platform(platform_func, email, client)
                if result and result["exists"]:
                    yield self.data(result)
                await asyncio.sleep(0.1)
