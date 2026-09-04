"""
Test suite for Strixy API endpoints.

This module tests Strixy service integration, data processing,
chat functionality, and error handling for the OSINT AI assistant
integration endpoints.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.exceptions import ValidationException
from app.schemas.strixy_schema import ChatResponse


class TestStrixyAPI:
    @pytest.fixture
    def auth_headers(self, user_token):
        return {"Authorization": f"Bearer {user_token}"}

    @patch("app.api.strixy.StrixyService")
    def test_chat_success(
        self, mock_service_class, client, auth_headers, test_case_with_users
    ):
        mock_service = Mock()
        mock_response = ChatResponse(
            message="Hello! How can I help with your OSINT investigation?",
            role="assistant",
            timestamp="2024-01-01T00:00:00",
        )
        mock_service.send_chat_message = AsyncMock(return_value=mock_response)
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/strixy/chat",
            json={
                "case_id": test_case_with_users.id,
                "messages": [{"role": "user", "content": "Hello"}],
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Hello! How can I help with your OSINT investigation?"
        assert data["role"] == "assistant"
        sent = mock_service.send_chat_message.call_args.args[0]
        assert [message.model_dump() for message in sent] == [
            {"role": "user", "content": "Hello"}
        ]

    def test_chat_unauthorized(self, client, test_case_with_users):
        response = client.post(
            "/api/strixy/chat",
            json={
                "case_id": test_case_with_users.id,
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        assert response.status_code == 401

    @patch("app.api.strixy.StrixyService")
    def test_chat_invalid_request(
        self, mock_service_class, client, auth_headers, test_case_with_users
    ):
        response = client.post(
            "/api/strixy/chat",
            json={
                "case_id": test_case_with_users.id,
                "messages": [{"role": "invalid_role", "content": "Hello"}],
            },
            headers=auth_headers,
        )

        assert response.status_code == 422

    @patch("app.api.strixy.StrixyService")
    def test_chat_service_error(
        self, mock_service_class, client, auth_headers, test_case_with_users
    ):
        mock_service = Mock()
        mock_service.send_chat_message.side_effect = ValidationException(
            "OpenAI API key not configured"
        )
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/strixy/chat",
            json={
                "case_id": test_case_with_users.id,
                "messages": [{"role": "user", "content": "Hello"}],
            },
            headers=auth_headers,
        )

        assert response.status_code == 422
        assert "OpenAI API key not configured" in response.json()["detail"]

    @patch("app.api.strixy.StrixyService")
    def test_chat_empty_messages(
        self, mock_service_class, client, auth_headers, test_case_with_users
    ):
        mock_service = Mock()
        mock_service.send_chat_message = AsyncMock(
            return_value=ChatResponse(
                message="How can I help?",
                role="assistant",
                timestamp="2024-01-01T00:00:00",
            )
        )
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/strixy/chat",
            json={"case_id": test_case_with_users.id, "messages": []},
            headers=auth_headers,
        )

        assert response.status_code == 200

    @pytest.mark.parametrize(
        "case_source, expected",
        [("inaccessible", 403), ("missing", 404), ("omitted", 422)],
    )
    @patch("app.api.strixy.StrixyService")
    def test_rejects_invalid_case_before_model_call(
        self, mock_service_class, client, auth_headers, test_case, case_source, expected
    ):
        payload = {"messages": [{"role": "user", "content": "Hello"}]}
        if case_source != "omitted":
            payload["case_id"] = (
                test_case.id if case_source == "inaccessible" else 99999
            )
        response = client.post("/api/strixy/chat", json=payload, headers=auth_headers)
        assert response.status_code == expected
        mock_service_class.assert_not_called()
