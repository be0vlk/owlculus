"""
Test suite for Strixy service business logic.

This module tests Strixy integration, data processing, error handling,
OpenAI API interaction, and OSINT-focused AI assistant functionality
within the Strixy service layer.
"""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.schemas.strixy_schema import ChatMessage
from app.services.api_key_vault import Provider, StaticApiKeyVault
from app.services.strixy_service import StrixyService


class TestStrixyService:
    @pytest.fixture
    def mock_db(self):
        return Mock()

    @pytest.fixture
    def strixy_service(self, mock_db):
        return StrixyService(
            mock_db, StaticApiKeyVault({Provider.OPENAI: "test-api-key"})
        )

    @patch("app.services.strixy_service.OpenAI")
    async def test_send_chat_message_success(self, mock_openai_class, strixy_service):
        mock_client = Mock()
        mock_completion = Mock()
        mock_completion.choices = [Mock()]
        mock_completion.choices[0].message.content = (
            "Hello! I'm Strixy, your OSINT assistant."
        )
        mock_client.chat.completions.create.return_value = mock_completion
        mock_openai_class.return_value = mock_client

        messages = [ChatMessage(role="user", content="Hello")]
        response = await strixy_service.send_chat_message(messages)

        assert response.message == "Hello! I'm Strixy, your OSINT assistant."
        assert response.role == "assistant"
        mock_openai_class.assert_called_once_with(api_key="test-api-key")

    async def test_send_chat_message_no_api_key(self, mock_db):
        strixy_service = StrixyService(mock_db, StaticApiKeyVault({}))
        messages = [ChatMessage(role="user", content="Hello")]

        with pytest.raises(HTTPException) as exc_info:
            await strixy_service.send_chat_message(messages)

        assert exc_info.value.status_code == 400
        assert "OpenAI API key not configured" in exc_info.value.detail

    @patch("app.services.strixy_service.OpenAI")
    async def test_send_chat_message_openai_error(
        self, mock_openai_class, strixy_service
    ):
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("OpenAI API Error")
        mock_openai_class.return_value = mock_client

        messages = [ChatMessage(role="user", content="Hello")]

        with pytest.raises(HTTPException) as exc_info:
            await strixy_service.send_chat_message(messages)

        assert exc_info.value.status_code == 500
        assert "Error communicating with OpenAI" in exc_info.value.detail

    @patch("app.services.strixy_service.OpenAI")
    async def test_client_reuse(self, mock_openai_class, strixy_service):
        mock_client = Mock()
        mock_completion = Mock()
        mock_completion.choices = [Mock()]
        mock_completion.choices[0].message.content = "Response"
        mock_client.chat.completions.create.return_value = mock_completion
        mock_openai_class.return_value = mock_client

        messages = [ChatMessage(role="user", content="Hello")]

        await strixy_service.send_chat_message(messages)
        await strixy_service.send_chat_message(messages)

        mock_openai_class.assert_called_once()
