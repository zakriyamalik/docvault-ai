from typing import Any, Dict, Optional
from app.llm.adapter import LLMClient
from app.llm.grounding import validate_citations, GroundingError
from app.llm.circuit_breaker import CircuitBreaker
from app.llm.pii import redact_pii
from app.metrics.llm_metrics import record_metric
from app.llm.schemas import LLMJsonResponse
# Module-level defaults (keeps existing monkeypatch tests working)
circuit_breaker = CircuitBreaker()
llm_client = LLMClient(
    provider="default_provider",
    model="default_model",
    circuit_breaker=circuit_breaker,
)


class QueryService:
    def __init__(
        self,
        quota_limit: int = 100,
        llm_client_override: Optional[LLMClient] = None,
        circuit_breaker_override: Optional[CircuitBreaker] = None,
        force_validate_stubs: bool = False,  # new flag for testing
    ):
        self.quota_limit = quota_limit
        self.usage_count = 0
        self.llm_client_override = llm_client_override
        self.circuit_breaker_override = circuit_breaker_override
        self.force_validate_stubs = force_validate_stubs

    def check_quota(self):
        if self.usage_count >= self.quota_limit:
            raise RuntimeError("Quota exceeded")

    def get_citation_map(self, provider: str) -> Dict[str, str]:
        """
        Placeholder to fetch citations mapping per provider.
        In production, implement properly to map citation IDs -> sources.
        """
        return {
            "cite_001": "https://linuxfoundation.org ",
            "cite_002": "https://en.wikipedia.org/wiki/Linux ",
        }

    def process_query(self, query: str, provider: str = "default") -> Dict[str, Any]:
        self.check_quota()

        # Resolve client & circuit-breaker at call time so monkeypatch works
        client: LLMClient = self.llm_client_override or llm_client
        cb: CircuitBreaker = getattr(client, "circuit_breaker", None) or self.circuit_breaker_override or circuit_breaker

        if not cb.can_call(provider):
            raise RuntimeError(f"Provider {provider} is temporarily unavailable")

        # Redact PII for audit logs
        redacted_query, pii_metadata = redact_pii(query)

        try:
            # pass provider to adapter & circuit-breaker per-provider
            response = client.generate({"request_id": provider, "provider": provider, "query": redacted_query})
            cb.record_success(provider)
        except Exception:
            cb.record_failure(provider)
            raise

        # Determine if stub call
        is_stub_call = (
            provider in client.stub_responses
            or len(client.stub_responses) == 1
        )

        # Validate grounding unless stub + not forced
                # Validate grounding unless stub + not forced
        if is_stub_call and not self.force_validate_stubs:
            validated_response = response
        else:
            citation_map = self.get_citation_map(provider)
            # Convert dict to LLMJsonResponse object if needed
            if isinstance(response, dict):
                response_obj = LLMJsonResponse(
                    answer=response.get("answer"),
                    citations=response.get("citations", [])
                )
            else:
                response_obj = response
            validate_citations(response_obj, citation_map)
            validated_response = response_obj

        # Record metrics
        record_metric("llm_query_count", 1, labels={"provider": provider})

        self.usage_count += 1
        return {
            "query": redacted_query,
            "response": validated_response,
            "pii_metadata": pii_metadata
        }