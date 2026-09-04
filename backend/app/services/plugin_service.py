"""Authorization, metadata, and production context adapters for plugins."""

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from typing import Any

from sqlmodel import Session

from app.database.models import User
from app.plugins.plugin_context import ProductionPluginRunAdapter
from app.plugins.plugin_registry import PluginRegistry, shipped_plugin_registry

from .api_key_vault import ApiKeyVault, ConfigurationApiKeyVault
from .case_access import CaseAccess


class PluginService:
    """Expose plugin metadata while keeping policy and persistence at the edge."""

    def __init__(
        self,
        db: Session,
        api_keys: ApiKeyVault | None = None,
        *,
        registry: PluginRegistry = shipped_plugin_registry,
        session_factory: Callable[[], AbstractContextManager[Session]] | None = None,
    ):
        self.db = db
        self.api_keys = api_keys or ConfigurationApiKeyVault(db)
        self.registry = registry
        run_vault_factory = (
            (lambda session: ConfigurationApiKeyVault(session))
            if api_keys is None or isinstance(api_keys, ConfigurationApiKeyVault)
            else (lambda _: self.api_keys)
        )
        self._run_adapter = ProductionPluginRunAdapter(
            session_factory or (lambda: nullcontext(self.db)), run_vault_factory
        )
        self.case_access = CaseAccess(db)

    def require_execution_access(self, current_user: User) -> None:
        self.case_access.require_non_analyst(current_user)

    def open_run(
        self, params: dict[str, Any], *, current_user: User
    ) -> AbstractContextManager:
        """Open the production context for the duration of streamed iteration."""
        case_id = params.get("case_id")
        return self._run_adapter.open(
            user=current_user,
            case_id=case_id if isinstance(case_id, int) else None,
            save_to_case=params.get("save_to_case") is True,
        )

    async def list_plugins(self, *, current_user: User) -> dict[str, Any]:
        self.require_execution_access(current_user)
        return self.registry.metadata(self.api_keys)
