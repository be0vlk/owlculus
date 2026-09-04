"""
Holehe plugin for checking email account registrations across platforms
"""

import asyncio
import importlib
from collections.abc import AsyncGenerator
from typing import Any

import httpx

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

    async def _get_holehe_modules(self):
        """Dynamically import all available holehe modules"""
        try:
            import pkgutil

            import holehe

            modules = []
            for importer, modname, ispkg in pkgutil.walk_packages(
                holehe.__path__, holehe.__name__ + "."
            ):
                if ispkg or modname.endswith(".__init__") or "core" in modname:
                    continue
                try:
                    module = importlib.import_module(modname)
                    func_name = modname.split(".")[-1]
                    if hasattr(module, func_name) and callable(
                        getattr(module, func_name)
                    ):
                        modules.append((func_name, getattr(module, func_name)))
                except (ImportError, AttributeError):
                    continue
            return modules
        except ImportError:
            return []

    async def _check_single_platform(
        self,
        platform_name: str,
        platform_func,
        email: str,
        client: httpx.AsyncClient,
        timeout: float,
    ) -> dict[str, Any]:
        """Check a single platform for email registration"""
        try:
            out: list[dict[str, Any]] = []
            client.timeout = httpx.Timeout(timeout)
            await platform_func(email, client, out)
            if out:
                result = out[0] if isinstance(out, list) else out
                return {
                    "platform": platform_name,
                    "email": email,
                    "exists": result.get("exists", False),
                    "partial_info": result.get("emailrecovery")
                    or result.get("phoneNumber"),
                    "ratelimited": result.get("ratelimit", False),
                    "error": result.get("error"),
                    "domain": result.get("domain", platform_name),
                }
            else:
                return {
                    "platform": platform_name,
                    "email": email,
                    "exists": False,
                    "error": "No response from platform",
                }
        except TimeoutError:
            return {
                "platform": platform_name,
                "email": email,
                "error": "Timeout",
                "ratelimited": True,
            }
        except Exception as e:
            return {"platform": platform_name, "email": email, "error": str(e)}

    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        """
        Execute holehe email checking with given parameters

        Args:
            params: Dictionary containing email and optional timeout

        Yields:
            Dictionary containing platform check results
        """
        if not params or "email" not in params:
            yield self.error("Email parameter is required")
            return
        email = params["email"].strip()
        timeout = params.get("timeout", 10.0)
        if not email:
            yield self.error("Email address cannot be empty")
            return
        modules = await self._get_holehe_modules()
        if not modules:
            return
        async with httpx.AsyncClient() as client:
            for platform_name, platform_func in modules:
                result = await self._check_single_platform(
                    platform_name, platform_func, email, client, timeout
                )
                if result.get("exists"):
                    yield self.data(result)
                await asyncio.sleep(0.1)
