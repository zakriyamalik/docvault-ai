import pytest

from app.llm.grounding import validate_citations, GroundingError
from app.llm.schemas import LLMJsonResponse


def make_response(citations):
    return LLMJsonResponse(answer="Test answer", citations=citations)


def test_valid_citations_pass():
    response = make_response(["doc:linux_history:p1"])
    citation_map = {"doc:linux_history:p1": "Linux history document"}

    # Should not raise
    validate_citations(response, citation_map)


def test_unknown_citation_fails():
    response = make_response(["doc:unknown:p9"])
    citation_map = {"doc:linux_history:p1": "Linux history document"}

    with pytest.raises(GroundingError):
        validate_citations(response, citation_map)


def test_missing_citations_fails():
    response = make_response([])
    citation_map = {"doc:linux_history:p1": "Linux history document"}

    with pytest.raises(GroundingError):
        validate_citations(response, citation_map)
