from __future__ import annotations

import time
import os
from typing import Any, Dict, Optional

from app.llm.circuit_breaker import CircuitBreaker, CircuitOpenError


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
        """Route to actual provider based on config."""
        from app.llm.schemas import LLMRequest, Message
        
        provider_name = payload.get("provider") or self.provider
        
        if provider_name == "groq":
            from app.llm.providers import GroqProvider
            
            groq_provider = GroqProvider()
            
            request = LLMRequest(
                provider="groq",
                model=payload.get("model", "llama3-8b-8192"),
                messages=[
                    Message(role="system", content=payload.get("system", "You are a helpful assistant.")),
                    Message(role="user", content=payload.get("query", ""))
                ],
                temperature=payload.get("temperature", 0.2),
                max_output_tokens=payload.get("max_tokens", 1024),
                request_id=payload.get("request_id")
            )
            
            result = groq_provider.generate(request)
            return {
                "answer": result.answer.text,
                "citations": [c.id for c in result.answer.citations],
                "usage": result.usage,
                "model": result.model,
                "latency_ms": result.latency_ms
            }
        
        else:
            raise NotImplementedError(f"Provider {provider_name} not implemented")

    def _call_stub(self, request_id: str) -> Dict[str, Any]:
        if request_id not in self.stub_responses:
            raise LLMTransportError(f"No stub for request_id={request_id}")
        return self.stub_responses[request_id]

    def generate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request_id = payload.get("request_id")
        provider = payload.get("provider") or self.provider

        if self.circuit_breaker.is_open(provider):
            raise CircuitOpenError(f"LLM circuit is open for provider={provider}")

        # Stub mode - only if explicitly requested
        if request_id and request_id in self.stub_responses:
            return self._call_stub(request_id)

        if provider in self.stub_responses:
            return self._call_stub(provider)

        # REMOVED: fallback to single stub when len(stub_responses) == 1
        # This was causing the bug where groq provider was ignored

        # Real provider with retries
        last_exc: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                start = time.time()
                response = self._call_provider(payload)
                latency_ms = int((time.time() - start) * 1000)
                response["latency_ms"] = latency_ms
                self.circuit_breaker.record_success(provider)
                return response
            except Exception as exc:
                last_exc = exc
                self.circuit_breaker.record_failure(provider)
                if attempt >= self.max_retries:
                    break

        raise LLMTransportError(f"LLM request failed after retries: {last_exc}")