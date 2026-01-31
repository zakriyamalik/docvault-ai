import re
from typing import List, Tuple, Dict

# Basic PII patterns; extendable
PII_PATTERNS: List[Tuple[str, re.Pattern, str]] = [
    ("email", re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), "[EMAIL]"),
    ("phone", re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'), "[PHONE]"),
    ("ssn", re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), "[SSN]"),
    ("credit_card", re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'), "[CC]"),
    ("ip", re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), "[IP]"),
]

def redact_pii(text: str) -> Tuple[str, List[Dict]]:
    """
    Redact all PII matches in the text.

    Returns:
        redacted_text, metadata_list
    metadata: [{type, position: (start, end), hash}]
    """
    redacted = text
    metadata: List[Dict] = []

    for pii_type, pattern, replacement in PII_PATTERNS:
        for match in reversed(list(pattern.finditer(redacted))):
            start, end = match.span()
            original = match.group()
            redacted = redacted[:start] + replacement + redacted[end:]
            metadata.append({
                "type": pii_type,
                "position": (start, end),
                "hash": hash(original) & 0xFFFFFFFF  # non-reversible
            })
    return redacted, metadata