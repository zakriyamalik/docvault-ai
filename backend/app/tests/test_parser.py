import pytest

from app.llm.parser import parse_llm_output, LLMParseError
from app.llm.schemas import LLMJsonResponse


VALID_JSON = '''{
  "answer": "Test answer",
  "citations": ["doc:linux_history:p1"]
}'''

INVALID_JSON = '''{
  "answer": "Broken JSON",
  "citations": ["doc:linux_history:p1"]
'''

EXTRA_FIELD_JSON = '''{
  "answer": "Test answer",
  "citations": ["doc:linux_history:p1"],
  "extra": "not allowed"
}'''


def test_parse_valid_json():
    result = parse_llm_output(VALID_JSON)
    assert isinstance(result, LLMJsonResponse)
    assert result.answer == "Test answer"


def test_parse_invalid_json_raises():
    with pytest.raises(LLMParseError):
        parse_llm_output(INVALID_JSON)


def test_extra_fields_forbidden():
    with pytest.raises(LLMParseError):
        parse_llm_output(EXTRA_FIELD_JSON)
