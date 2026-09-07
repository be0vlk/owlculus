"""Small public interface implemented by investigation plugin authors."""

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Mapping, Sequence
from typing import Any

from app.core.utils import get_utc_now
from app.schemas.evidence_schema import EvidenceCreate
from app.services.api_key_vault import ApiKeyVault, Provider

from .output_limits import OutputBudget
from .plugin_context import PluginRun
from .plugin_types import (
    EntityWrite,
    EvidenceWrite,
    Payload,
    ResultEvent,
    unique_ip_writes,
)
from .subprocess_plugin import SubprocessPluginMixin

__all__ = [
    "BasePlugin",
    "EntityWrite",
    "EvidenceWrite",
    "Payload",
    "PluginRun",
    "ResultEvent",
    "SubprocessPluginMixin",
    "unique_ip_writes",
]


class BasePlugin(ABC):
    """Metadata, event constructors, and result collection shared by plugins."""

    def __init__(self, display_name: str | None = None):
        self.name = self.__class__.__name__
        self.display_name = display_name or self.name
        self.description = ""
        self.enabled = True
        self.category = "Other"
        self.evidence_category = "Other"
        self.parameters: dict[str, dict[str, Any]] = {}
        self.api_key_requirements: list[Provider] = []

    @staticmethod
    def data(payload: Mapping[str, Any]) -> ResultEvent:
        return ResultEvent.data(payload)

    @staticmethod
    def error(message: str) -> ResultEvent:
        return ResultEvent.error(message)

    @staticmethod
    def status(message: str) -> ResultEvent:
        return ResultEvent.status(message)

    @staticmethod
    def complete() -> ResultEvent:
        return ResultEvent.complete()

    @abstractmethod
    def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]: ...

    async def execute_with_evidence_collection(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        budget = OutputBudget()
        payloads: list[Payload] = []
        async for event in self.run(params, ctx):
            budget.accept(event)
            if ctx.save_to_case and event.kind == "data":
                payloads.append(event.payload)
            yield event

        if not ctx.save_to_case or ctx.case_id is None or not payloads:
            return
        content = self.format_evidence(payloads, params)
        if content:
            timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
            # Keep normal evidence formatting; large documents use ordered parts
            # below the upload service's existing file size limit (even in UTF-8).
            part_size = 2 * 1024 * 1024
            for index, offset in enumerate(range(0, len(content), part_size), 1):
                suffix = f"_part_{index:04d}" if len(content) > part_size else ""
                await ctx.evidence.write(
                    EvidenceWrite(
                        self.name,
                        self.display_name + (f" part {index}" if suffix else ""),
                        self.evidence_category,
                        ctx.case_id,
                        content[offset : offset + part_size],
                        f"{self.name}_results_{timestamp}{suffix}.txt",
                        correlation_case_ids=self.correlation_case_ids(
                            payloads, ctx.case_id
                        ),
                    ),
                    ctx.user,
                )
        for request in self.entity_writes(payloads, params):
            warning = await ctx.entities.write(request, ctx.case_id, ctx.user)
            if warning:
                yield self.data(
                    {"notice_type": "entity_save_skipped", "message": warning}
                )

    def correlation_case_ids(
        self, payloads: list[Payload], case_id: int
    ) -> tuple[int, ...] | None:
        return None

    def format_evidence(self, payloads: list[Payload], params: dict[str, Any]) -> str:
        lines = [
            f"{self.display_name} Results",
            "=" * 50,
            "",
            f"Total results: {len(payloads)}",
            f"Execution time: {get_utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "Parameters:",
            "-" * 20,
        ]
        lines.extend(
            f"{key}: {value}"
            for key, value in params.items()
            if key not in {"save_to_case", "case_id"}
        )
        lines.extend(["", "Results:", "-" * 20, ""])
        for index, payload in enumerate(payloads, 1):
            lines.extend(
                [f"Result #{index}:", json.dumps(payload, indent=2, default=str), ""]
            )
        return "\n".join(lines)

    def entity_writes(
        self, payloads: list[Payload], params: dict[str, Any]
    ) -> Sequence[EntityWrite]:
        return []

    def _generate_ip_description(self, ip_address: str, context: str = "") -> str:
        context_part = f" for '{context}'" if context else ""
        return f"Discovered via {self.display_name} lookup{context_part}"

    def _get_enhanced_parameters(self) -> dict[str, dict[str, Any]]:
        parameters = self.parameters.copy()
        parameters.setdefault(
            "save_to_case",
            {
                "type": "boolean",
                "description": f"Save {self.display_name} results as evidence to the case",
                "default": False,
                "required": False,
            },
        )
        return parameters

    def get_metadata(self, api_keys: ApiKeyVault | None = None) -> dict[str, Any]:
        if self.evidence_category not in EvidenceCreate.VALID_CATEGORIES:
            raise ValueError(f"Invalid evidence category: {self.evidence_category}")
        metadata: dict[str, Any] = {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "enabled": self.enabled,
            "category": self.category,
            "parameters": self._get_enhanced_parameters(),
            "api_key_requirements": self.api_key_requirements,
        }
        if api_keys is not None:
            metadata["api_key_status"] = {
                provider.value: api_keys.is_configured(provider)
                for provider in self.api_key_requirements
            }
        return metadata
