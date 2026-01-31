# app/llm/adapter.py
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from app.llm.circuit_breaker import CircuitBreaker, CircuitOpenError

# -----------------------------
# LLM Client Adapter
# - Transport retries
# - Circuit breaker protection
# - Deterministic stub mode
# -----------------------------


class LLMTransportError(Exception):
    pass


class LLMClient:
    def __init__(
        self,
        provider: str,
        model: str,
        circuit_breaker: CircuitBreaker,
        max_retries: int = 2,
        stub_responses: Optional[Dict[str, Any]] = None,
    ):
        self.provider = provider
        self.model = model
        self.circuit_breaker = circuit_breaker
        self.max_retries = max_retries
        self.stub_responses = stub_responses or {}

    def _call_provider(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Actual provider call placeholder.
        Must be implemented per provider.
        """
        raise NotImplementedError

    def _call_stub(self, request_id: str) -> Dict[str, Any]:
        if request_id not in self.stub_responses:
            raise LLMTransportError(f"No stub for request_id={request_id}")
        return self.stub_responses[request_id]

    def generate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        payload may include:
            - request_id: (optional) stub id
            - provider: (optional) override provider key
            - other provider-specific fields
        """
        request_id = payload.get("request_id")
        provider = payload.get("provider") or self.provider

        # Circuit check per provider
        if self.circuit_breaker.is_open(provider):
            raise CircuitOpenError(f"LLM circuit is open for provider={provider}")

        # Stub mode — robust lookup
        if request_id and request_id in self.stub_responses:
            return self._call_stub(request_id)

        if provider in self.stub_responses:
            return self._call_stub(provider)

        if len(self.stub_responses) == 1:
            return next(iter(self.stub_responses.values()))

        # No stub found — try real provider with retries
        last_exc: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                start = time.time()
                response = self._call_provider(payload)
                latency_ms = int((time.time() - start) * 1000)
                response["latency_ms"] = latency_ms
                # record success for the provider we just used
                self.circuit_breaker.record_success(provider)
                return response
            except Exception as exc:  # transport-level only
                last_exc = exc
                self.circuit_breaker.record_failure(provider)
                if attempt >= self.max_retries:
                    break

        raise LLMTransportError(f"LLM request failed after retries: {last_exc}")
