from __future__ import annotations

import json
from typing import Any

from .schemas import LLMJsonResponse


class LLMParseError(Exception):
    """Raised when LLM output is not strictly valid JSON or schema-compliant."""
    pass


class ExtraFieldError(LLMParseError):
    pass


class CitationFormatError(LLMParseError):
    pass


def parse_llm_output(raw: str) -> LLMJsonResponse:
    """
    STRICT parser:
    - Accepts ONLY valid JSON objects
    - Strips outer markdown fences ONLY (```json ... ```)
    - No regex guessing, no partial extraction
    """
    if not raw or not isinstance(raw, str):
        raise LLMParseError("Empty or non-string LLM output")

    text = raw.strip()

    # Strip markdown fences (outer only)
    if text.startswith("```"):
        text = text.split("```", 2)[1].strip()

    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMParseError(f"Invalid JSON: {e}")

    if not isinstance(payload, dict):
        raise LLMParseError("JSON root must be an object")

    try:
        return LLMJsonResponse.model_validate(payload)
    except Exception as e:
        msg = str(e).lower()
        if "extra fields" in msg or "extra_forbid" in msg:
            raise ExtraFieldError(str(e))
        if "citation" in msg:
            raise CitationFormatError(str(e))
        raise LLMParseError(str(e))
