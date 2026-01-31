import pytest
import json
from app.services.query_service import QueryService
from app.llm.adapter import LLMClient
from app.llm.circuit_breaker import CircuitBreaker
from app.llm.grounding import GroundingError
from app.llm.schemas import LLMJsonResponse

@pytest.fixture
def stub_client():
    cb = CircuitBreaker()
    return LLMClient(
        provider="stub",
        model="stub-model",
        circuit_breaker=cb,
        stub_responses={
            "stub": {
                "text": "stub answer",
                "citations": []
            }
        },
    )


def test_query_service_happy_path(monkeypatch, stub_client):
    service = QueryService(quota_limit=10)

    # Updated monkeypatch path for Docker
    monkeypatch.setattr(
        "app.services.query_service.llm_client",
        stub_client,
    )

    query = "Explain Linux evolution"

    result = service.process_query(
        query=query,
        provider="stub",
    )

    assert "response" in result
    assert result["response"]["text"] == "stub answer"


def test_query_service_grounding_failure(monkeypatch):
    # Updated fixture path for Docker
    with open("app/tests/fixtures/llm_stub_invalid_citation.json") as f:
        invalid_stub = json.load(f)

    cb = CircuitBreaker()
    client = LLMClient(
        provider="stub",
        model="stub-model",
        circuit_breaker=cb,
        stub_responses={"test_invalid_citation_001": invalid_stub},
    )

    service = QueryService(quota_limit=10, force_validate_stubs=True)

    # Updated monkeypatch path for Docker
    monkeypatch.setattr(
        "app.services.query_service.llm_client",
        client,
    )

    with pytest.raises(GroundingError):
        service.process_query(
            query="test query",
            provider="test_invalid_citation_001",
        )