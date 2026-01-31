from __future__ import annotations

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

# -----------------------------
# Canonical request/response schemas for LLM interactions
# Strict validation: extra fields forbidden
# -----------------------------

MAX_PROMPT_CHARS = 24_000
MAX_CONTEXT_CHARS = 48_000
MAX_OUTPUT_TOKENS = 4_096


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Message(_StrictModel):
    role: str = Field(..., description="system|user|assistant")
    content: str = Field(..., min_length=1)

    @field_validator("role")
    @classmethod
    def role_allowed(cls, v: str) -> str:
        if v not in {"system", "user", "assistant"}:
            raise ValueError("invalid role")
        return v


class LLMRequest(_StrictModel):
    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    messages: List[Message]
    temperature: float = Field(0.2, ge=0.0, le=2.0)
    max_output_tokens: int = Field(MAX_OUTPUT_TOKENS, ge=1, le=MAX_OUTPUT_TOKENS)
    citation_map: Optional[Dict[str, Any]] = Field(
        default=None, description="id -> source metadata used for grounding"
    )
    request_id: Optional[str] = None

    @field_validator("messages")
    @classmethod
    def size_limits(cls, v: List[Message]) -> List[Message]:
        total = sum(len(m.content) for m in v)
        if total > MAX_CONTEXT_CHARS:
            raise ValueError("context too large")
        return v


class Citation(_StrictModel):
    id: str
    quote: str


class LLMAnswer(_StrictModel):
    text: str = Field(..., min_length=1)
    citations: List[Citation] = Field(default_factory=list)


class LLMResponse(_StrictModel):
    provider: str
    model: str
    answer: LLMAnswer
    usage: Dict[str, int] = Field(
        ..., description="token usage e.g. prompt_tokens, completion_tokens"
    )
    latency_ms: int = Field(..., ge=0)
    request_id: Optional[str] = None
class LLMJsonResponse(_StrictModel):
    answer: str
    citations: List[str]
