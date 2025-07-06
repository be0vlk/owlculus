from unittest.mock import Mock, patch

import pytest
from app.main import app
from app.schemas.strixy_schema import ChatResponse
from fastapi import HTTPException
from fastapi.testclient import TestClient


class TestStrixyAPI:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, test_user_token):
        return {"Authorization": f"Bearer {test_user_token}"}

    @patch("app.api.strixy.StrixyService")
    def test_chat_success(self, mock_service_class, client, auth_headers):
        mock_service = Mock()
        mock_response = ChatResponse(
            message="Hello! How can I help with your OSINT investigation?",
            role="assistant",
            timestamp="2024-01-01T00:00:00",
        )
        mock_service.send_chat_message.return_value = mock_response
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/strixy/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Hello! How can I help with your OSINT investigation?"
        assert data["role"] == "assistant"

    def test_chat_unauthorized(self, client):
        response = client.post(
            "/api/strixy/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )

        assert response.status_code == 401

    @patch("app.api.strixy.StrixyService")
    def test_chat_invalid_request(self, mock_service_class, client, auth_headers):
        response = client.post(
            "/api/strixy/chat",
            json={"messages": [{"role": "invalid_role", "content": "Hello"}]},
            headers=auth_headers,
        )

        assert response.status_code == 422

    @patch("app.api.strixy.StrixyService")
    def test_chat_service_error(self, mock_service_class, client, auth_headers):
        mock_service = Mock()
        mock_service.send_chat_message.side_effect = HTTPException(
            status_code=400, detail="OpenAI API key not configured"
        )
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/strixy/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "OpenAI API key not configured" in response.json()["detail"]

    def test_chat_empty_messages(self, client, auth_headers):
        response = client.post(
            "/api/strixy/chat", json={"messages": []}, headers=auth_headers
        )

        assert response.status_code == 200
