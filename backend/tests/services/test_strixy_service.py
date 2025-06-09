import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException

from app.services.strixy_service import StrixyService
from app.schemas.strixy_schema import ChatMessage


class TestStrixyService:
    @pytest.fixture
    def mock_db(self):
        return Mock()

    @pytest.fixture
    def strixy_service(self, mock_db):
        return StrixyService(mock_db)

    @patch("app.services.strixy_service.SystemConfigService")
    @patch("app.services.strixy_service.OpenAI")
    async def test_send_chat_message_success(
        self, mock_openai_class, mock_config_service_class, strixy_service
    ):
        mock_config_service = Mock()
        mock_config_service.get_api_key.return_value = "test-api-key"
        mock_config_service_class.return_value = mock_config_service

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
        mock_config_service.get_api_key.assert_called_once_with("openai")
        mock_openai_class.assert_called_once_with(api_key="test-api-key")

    @patch("app.services.strixy_service.SystemConfigService")
    async def test_send_chat_message_no_api_key(
        self, mock_config_service_class, strixy_service
    ):
        mock_config_service = Mock()
        mock_config_service.get_api_key.return_value = None
        mock_config_service_class.return_value = mock_config_service

        messages = [ChatMessage(role="user", content="Hello")]

        with pytest.raises(HTTPException) as exc_info:
            await strixy_service.send_chat_message(messages)

        assert exc_info.value.status_code == 400
        assert "OpenAI API key not configured" in exc_info.value.detail

    @patch("app.services.strixy_service.SystemConfigService")
    @patch("app.services.strixy_service.OpenAI")
    async def test_send_chat_message_openai_error(
        self, mock_openai_class, mock_config_service_class, strixy_service
    ):
        mock_config_service = Mock()
        mock_config_service.get_api_key.return_value = "test-api-key"
        mock_config_service_class.return_value = mock_config_service

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("OpenAI API Error")
        mock_openai_class.return_value = mock_client

        messages = [ChatMessage(role="user", content="Hello")]

        with pytest.raises(HTTPException) as exc_info:
            await strixy_service.send_chat_message(messages)

        assert exc_info.value.status_code == 500
        assert "Error communicating with OpenAI" in exc_info.value.detail

    @patch("app.services.strixy_service.SystemConfigService")
    @patch("app.services.strixy_service.OpenAI")
    async def test_client_reuse(
        self, mock_openai_class, mock_config_service_class, strixy_service
    ):
        mock_config_service = Mock()
        mock_config_service.get_api_key.return_value = "test-api-key"
        mock_config_service_class.return_value = mock_config_service

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
        assert mock_config_service.get_api_key.call_count == 1
