"""Small stateless OpenAI Responses adapter; application state stays in PostgreSQL."""

from dataclasses import dataclass
from typing import cast

from openai import OpenAI
from openai.types.responses import ResponseInputParam
from sqlmodel import Session

from app.core.exceptions import ValidationException
from app.core.strixy_config import StrixyConfig
from app.schemas.strixy_schema import ChatMessage
from app.services.api_key_vault import ApiKeyVault, ConfigurationApiKeyVault, Provider


@dataclass(frozen=True)
class ProviderReply:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    limit_code: str | None = None


class StrixyService:
    def __init__(self, db: Session, api_key_vault: ApiKeyVault | None = None):
        self.api_key_vault = api_key_vault or ConfigurationApiKeyVault(db)

    def generate(
        self, messages: list[ChatMessage], config: StrixyConfig, timeout: float
    ) -> ProviderReply:
        key = self.api_key_vault.get_key(Provider.OPENAI)
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
        if not response.output_text and not limit:
            raise RuntimeError("Provider returned no answer")
        return ProviderReply(
            content=response.output_text,
            input_tokens=response.usage.input_tokens if response.usage else 0,
            output_tokens=response.usage.output_tokens if response.usage else 0,
            limit_code=limit,
        )
