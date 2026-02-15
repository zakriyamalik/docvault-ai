import time
from typing import Any, Dict, Optional, List

from app.llm.adapter import LLMClient
from app.llm.grounding import validate_citations, GroundingError
from app.llm.circuit_breaker import CircuitBreaker
from app.llm.pii import redact_pii
from app.metrics.llm_metrics import record_metric
from app.llm.schemas import LLMJsonResponse
from app.retrieval.retriever import retrieve, Chunk
import os
import logging

logger = logging.getLogger(__name__)
circuit_breaker = CircuitBreaker()

llm_client = LLMClient(
    provider=os.getenv("LLM_PROVIDER", "groq"),
    model=os.getenv("LLM_MODEL", "llama-3.1-8b-instant"),
    circuit_breaker=circuit_breaker,
    stub_responses={}
)

class QueryService:
    def __init__(
        self,
        quota_limit: int = 100,
        llm_client_override: Optional[LLMClient] = None,
        circuit_breaker_override: Optional[CircuitBreaker] = None,
        force_validate_stubs: bool = False,
        top_k_retrieval: int = 5,
    ):
        self.quota_limit = quota_limit
        self.usage_count = 0
        self.llm_client_override = llm_client_override
        self.circuit_breaker_override = circuit_breaker_override
        self.force_validate_stubs = force_validate_stubs
        self.top_k_retrieval = top_k_retrieval

    def check_quota(self):
        if self.usage_count >= self.quota_limit:
            raise RuntimeError(f"Quota exceeded ({self.usage_count}/{self.quota_limit})")

    def reset_quota(self):
        self.usage_count = 0

    def get_citation_map(self, provider: str) -> Dict[str, str]:
        return {
            "cite_001": "https://linuxfoundation.org",
            "cite_002": "https://en.wikipedia.org/wiki/Linux",
        }

    def _build_context_from_chunks(self, chunks: List[Chunk]) -> str:
        if not chunks:
            return ""

        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            chunk_index = None
            if chunk.metadata and isinstance(chunk.metadata, dict):
                chunk_index = chunk.metadata.get("chunk_index")
            preview = (chunk.content or "")[:400]
            if chunk_index is None:
                context_parts.append(f"[{i}] Source: {chunk.document_id}\n{preview}")
            else:
                context_parts.append(f"[{i}] Source: {chunk.document_id} (chunk {chunk_index})\n{preview}")

        return "\n\n".join(context_parts)

    def process_query(
        self,
        query: str,
        provider: str = "default",
        context: Optional[str] = None,
        use_retrieval: bool = True,
    ) -> Dict[str, Any]:
        self.check_quota()

        retrieved_chunks: List[Chunk] = []
        sources: List[Dict[str, Any]] = []

        if use_retrieval:
            try:
                retrieved_chunks = retrieve(query, top_k=self.top_k_retrieval)
                sources = [ {
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "score": c.score,
                    "metadata": c.metadata
                } for c in retrieved_chunks ]
            except Exception as e:
                logger.exception("[RAG] Retrieval failed")
                print(f"[RAG] Retrieval failed: {e}")

        chunk_context = self._build_context_from_chunks(retrieved_chunks)

        if use_retrieval and chunk_context:
            full_prompt = (
                f"You are a document Q&A assistant. Answer ONLY using the provided context. "
                f"Cite sources using [1], [2], etc. If unsure, say 'I don't know based on the documents.'\n\n"
                f"Context:\n{chunk_context}\n\n"
                f"Question: {query}\n\n"
                f"Answer:"
            )
        else:
            full_prompt = (
                f"You are a helpful assistant. Answer the question and cite any factual claims "
                f"using [1], [2], etc. referencing authoritative sources.\n\n"
                f"Question: {query}\n\n"
                f"Answer:"
            )

        redacted_query, pii_metadata = redact_pii(query)

        if use_retrieval and chunk_context:
            full_prompt, _ = redact_pii(full_prompt)

        client: LLMClient = self.llm_client_override or llm_client

        llm_provider = os.getenv("LLM_PROVIDER", "stub")
        llm_model = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

        try:
            response = client.generate({
                "request_id": f"req_{hash(query + str(time.time()))}",
                "provider": llm_provider,
                "model": llm_model,
                "query": full_prompt,
                "temperature": 0.3,
                "system": "You are a helpful document assistant.",
            })
        except GroundingError:
            raise
        except Exception as e:
            raise RuntimeError(f"LLM call failed: {str(e)}") from e

        is_stub_call = llm_provider == "stub"

        if isinstance(response, dict):
            answer = response.get("answer")
            if answer is None:
                raise ValueError("LLM response missing 'answer' field")
            response_obj = LLMJsonResponse(
                answer=answer,
                citations=response.get("citations", [])
            )
        elif isinstance(response, LLMJsonResponse):
            response_obj = response
        else:
            raise TypeError(f"Unexpected response type: {type(response)}")

        record_metric("llm_query_count", 1, labels={"provider": llm_provider})

        self.usage_count += 1

        return {
            "query": redacted_query,
            "response": response_obj,
            "pii_metadata": pii_metadata,
            "was_stub": is_stub_call,
            "sources": sources,
            "retrieved_chunks": len(retrieved_chunks),
            "model_used": getattr(response, "model", "unknown"),
        }
