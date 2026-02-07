import os
import pytest
from fastapi.testclient import TestClient

# Set deterministic env before importing app
os.environ["LLM_PROVIDER"] = "stub"
os.environ["EMBEDDING_STUB"] = "true"
os.environ["EVAL_SEED"] = "1337"

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def stub_llm_response(monkeypatch):
    """Ensure deterministic stub responses."""
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("EMBEDDING_STUB", "true")


class TestChatAPI:
    """Test chat API endpoints end-to-end."""

    def test_start_chat_returns_conversation_id(self, client, stub_llm_response):
        """POST /api/v1/chat/start returns conversation_id."""
        response = client.post(
            "/api/v1/chat/start",
            json={
                "first_message": "What is email etiquette?",
                "title_preview": "Email Question",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "conversation_id" in data
        assert len(data["conversation_id"]) > 0
        assert data["title"] == "Email Question"
        assert "first_message_id" in data

    def test_start_chat_without_title_preview(self, client, stub_llm_response):
        """POST /api/v1/chat/start auto-generates title from message."""
        response = client.post(
            "/api/v1/chat/start",
            json={"first_message": "How to write professional emails?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "conversation_id" in data
        # Title auto-generated from first 100 chars
        assert "How to write professional emails?" in data["title"]

    def test_send_message_returns_answer_and_sources(self, client, stub_llm_response):
        """POST /api/v1/chat/{id}/message returns answer + sources."""
        # First create conversation
        start_resp = client.post(
            "/api/v1/chat/start",
            json={"first_message": "Test message"},
        )
        conv_id = start_resp.json()["conversation_id"]

        # Send follow-up message
        response = client.post(
            f"/api/v1/chat/{conv_id}/message",
            json={"content": "Tell me more about email"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == conv_id
        assert "message_id" in data
        assert data["role"] == "assistant"
        assert "content" in data
        assert isinstance(data["sources"], list)

    def test_send_message_404_for_invalid_conversation(self, client, stub_llm_response):
        """POST /api/v1/chat/{id}/message returns 404 for invalid conversation."""
        response = client.post(
            "/api/v1/chat/invalid-uuid/message",
            json={"content": "Test message"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_history_returns_persisted_messages(self, client, stub_llm_response):
        """GET /api/v1/chat/{id}/history returns messages persisted."""
        # Create conversation
        start_resp = client.post(
            "/api/v1/chat/start",
            json={"first_message": "Initial question about email?"},
        )
        conv_id = start_resp.json()["conversation_id"]

        # Send another message
        client.post(
            f"/api/v1/chat/{conv_id}/message",
            json={"content": "Follow up question"},
        )

        # Get history
        response = client.get(f"/api/v1/chat/{conv_id}/history")

        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == conv_id
        assert "messages" in data
        assert len(data["messages"]) >= 2  # At least user + assistant from start

        # Verify message structure
        for msg in data["messages"]:
            assert "message_id" in msg
            assert "role" in msg
            assert msg["role"] in ["user", "assistant"]
            assert "content" in msg
            assert "timestamp" in msg

    def test_get_history_404_for_invalid_conversation(self, client, stub_llm_response):
        """GET /api/v1/chat/{id}/history returns 404 for invalid conversation."""
        response = client.get("/api/v1/chat/nonexistent-uuid/history")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_list_conversations(self, client, stub_llm_response):
        """GET /api/v1/chat/conversations returns all conversations."""
        # Create a conversation first
        client.post(
            "/api/v1/chat/start",
            json={"first_message": "Test conversation"},
        )

        response = client.get("/api/v1/chat/conversations")

        assert response.status_code == 200
        data = response.json()
        assert "conversations" in data
        assert isinstance(data["conversations"], list)

    def test_delete_conversation(self, client, stub_llm_response):
        """DELETE /api/v1/chat/{id} removes conversation."""
        # Create conversation
        start_resp = client.post(
            "/api/v1/chat/start",
            json={"first_message": "To be deleted"},
        )
        conv_id = start_resp.json()["conversation_id"]

        # Delete it
        response = client.delete(f"/api/v1/chat/{conv_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify it's gone
        history_resp = client.get(f"/api/v1/chat/{conv_id}/history")
        assert history_resp.status_code == 404

    def test_chat_flow_end_to_end(self, client, stub_llm_response):
        """Full flow: start → message → history → delete."""
        # 1. Start conversation
        start_resp = client.post(
            "/api/v1/chat/start",
            json={"first_message": "What is professional email etiquette?"},
        )
        assert start_resp.status_code == 200
        conv_id = start_resp.json()["conversation_id"]

        # 2. Send multiple messages
        for i in range(3):
            msg_resp = client.post(
                f"/api/v1/chat/{conv_id}/message",
                json={"content": f"Follow up question {i+1}"},
            )
            assert msg_resp.status_code == 200
            assert "content" in msg_resp.json()

        # 3. Verify history has all messages
        history_resp = client.get(f"/api/v1/chat/{conv_id}/history")
        assert history_resp.status_code == 200
        messages = history_resp.json()["messages"]
        assert len(messages) >= 4  # 1 start + 3 follow-ups (user+assistant pairs)

        # 4. Delete conversation
        del_resp = client.delete(f"/api/v1/chat/{conv_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"
