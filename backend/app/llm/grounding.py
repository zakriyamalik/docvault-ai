from __future__ import annotations

from typing import Dict, Set

from .schemas import LLMJsonResponse


class GroundingError(Exception):
    """Raised when citations do not match provided grounding sources."""
    pass


def validate_citations(
    response: LLMJsonResponse,
    citation_map: Dict[str, str],
) -> None:
    """
    Validates that:
    - Every cited reference exists in citation_map
    - No uncited sources are claimed

    citation_map: {citation_id -> source_string}
    """
    if not citation_map:
        raise GroundingError("citation_map is empty")

    cited: Set[str] = set(response.citations or [])
    allowed: Set[str] = set(citation_map.keys())

    missing = cited - allowed
    if missing:
        raise GroundingError(f"Unknown citation ids: {sorted(missing)}")

    # Optional strictness: require at least one citation when grounding enabled
    if not cited:
        raise GroundingError("No citations provided in grounded response")
