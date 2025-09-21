"""
Holehe plugin for checking email account registrations across platforms
"""

import asyncio
import importlib
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from sqlmodel import Session

from .base_plugin import BasePlugin


class HolehePlugin(BasePlugin):
    """Plugin to check if email addresses are registered on various platforms using Holehe"""

    def __init__(self, db_session: Session = None):
        super().__init__(display_name="Holehe", db_session=db_session)
        self.description = "Check if email addresses are registered on 120+ platforms using account recovery verification"
        self.category = "Person"
        self.evidence_category = "Social Media"
        self.save_to_case = True
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

    def parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        """Not used as holehe queries are handled directly"""
        return None

    async def _get_holehe_modules(self):
        """Dynamically import all available holehe modules"""
        try:
            import pkgutil

            import holehe

            modules = []

            # Walk through all holehe modules
            for importer, modname, ispkg in pkgutil.walk_packages(
                holehe.__path__, holehe.__name__ + "."
            ):
                if ispkg or modname.endswith(".__init__") or "core" in modname:
                    continue

                try:
                    module = importlib.import_module(modname)

                    # Get the function name from the module name (last part)
                    func_name = modname.split(".")[-1]

                    # Check if the module has the expected function
                    if hasattr(module, func_name) and callable(
                        getattr(module, func_name)
                    ):
                        modules.append((func_name, getattr(module, func_name)))

                except (ImportError, AttributeError):
                    # Skip modules that can't be imported or don't have the expected function
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
    ) -> Dict[str, Any]:
        """Check a single platform for email registration"""
        try:
            out = []

            # Set timeout for this specific check
            client.timeout = httpx.Timeout(timeout)

            # Call the platform function
            await platform_func(email, client, out)

            # Parse the result
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

        except asyncio.TimeoutError:
            return {
                "platform": platform_name,
                "email": email,
                "error": "Timeout",
                "ratelimited": True,
            }
        except Exception as e:
            return {
                "platform": platform_name,
                "email": email,
                "error": str(e),
            }

    async def run(
        self, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute holehe email checking with given parameters

        Args:
            params: Dictionary containing email and optional timeout

        Yields:
            Dictionary containing platform check results
        """
        if not params or "email" not in params:
            yield {"type": "error", "data": {"message": "Email parameter is required"}}
            return

        email = params["email"].strip()
        timeout = params.get("timeout", 10.0)

        if not email:
            yield {
                "type": "error",
                "data": {"message": "Email address cannot be empty"},
            }
            return

        # Get available holehe modules
        modules = await self._get_holehe_modules()

        if not modules:
            return

        # Check each platform - only yield found accounts
        async with httpx.AsyncClient() as client:
            for platform_name, platform_func in modules:
                result = await self._check_single_platform(
                    platform_name, platform_func, email, client, timeout
                )

                # Only yield results where account exists (found)
                if result.get("exists"):
                    yield {
                        "type": "data",
                        "data": result,
                    }

                # Small delay between requests to be respectful
                await asyncio.sleep(0.1)
