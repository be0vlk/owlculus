"""Small stateless OpenAI Responses adapter; application state stays in PostgreSQL."""

import json
from dataclasses import dataclass, field
from typing import cast

from openai import OpenAI
from openai.types.responses import ResponseInputParam
from sqlmodel import Session

from app.core.exceptions import ValidationException
from app.core.strixy_config import StrixyConfig
from app.schemas.strixy_schema import ChatMessage, GroundedAnswer, SourceQuery
from app.services.api_key_vault import ApiKeyVault, ConfigurationApiKeyVault, Provider


@dataclass(frozen=True)
class ProviderReply:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    limit_code: str | None = None
    citations: list[dict] = field(default_factory=list)
    tool_requests: list[dict] = field(default_factory=list)


class StrixyService:
    def __init__(self, db: Session, api_key_vault: ApiKeyVault | None = None):
        vault = api_key_vault or ConfigurationApiKeyVault(db)
        self.api_key = vault.get_key(Provider.OPENAI)

    def generate(
        self, messages: list[ChatMessage], config: StrixyConfig, timeout: float
    ) -> ProviderReply:
        key = self.api_key
        if not key:
            raise ValidationException("OpenAI API key not configured")
        # No SDK retries: an uncertain completion must require explicit human action.
        with OpenAI(api_key=key, max_retries=0, timeout=timeout) as client:
            response = client.responses.create(
                model=config.model,
                instructions=config.instructions,
                input=cast(ResponseInputParam, [m.model_dump() for m in messages]),
                max_output_tokens=config.max_output_tokens,
                store=False,
                tools=[
                    {
                        "type": "function",
                        "name": "read_case_sources",
                        "description": "List, search or read the bounded authorized Case sources. No Case or identity overrides.",
                        "parameters": SourceQuery.model_json_schema(),
                        "strict": True,
                    }
                ],
                parallel_tool_calls=False,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "grounded_answer",
                        "schema": GroundedAnswer.model_json_schema(),
                        "strict": True,
                    }
                },
            )
        limit = None
        if (
            response.status == "incomplete"
            and response.incomplete_details
            and response.incomplete_details.reason == "max_output_tokens"
        ):
            limit = "output_limit"
        elif response.status != "completed":
            raise RuntimeError("Provider did not complete the response")
        requests = [
            {"name": item.name, "arguments": json.loads(item.arguments)}
            for item in response.output
            if item.type == "function_call"
        ]
        if not response.output_text and not limit and not requests:
            raise RuntimeError("Provider returned no answer")
        # Incomplete JSON cannot be safely exposed as a grounded answer.
        answer = (
            GroundedAnswer.model_validate_json(response.output_text)
            if response.output_text and not limit
            else None
        )
        return ProviderReply(
            content=answer.content if answer else "",
            citations=[c.model_dump() for c in answer.citations] if answer else [],
            tool_requests=requests,
            input_tokens=response.usage.input_tokens if response.usage else 0,
            output_tokens=response.usage.output_tokens if response.usage else 0,
            limit_code=limit,
        )
