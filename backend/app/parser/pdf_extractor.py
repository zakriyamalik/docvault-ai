from pathlib import Path
from typing import List
import re

import fitz  # PyMuPDF

from .base import PageText


def _normalize_text(text: str) -> str:
    # Remove null characters
    text = text.replace("\x00", "")
    # Normalize Windows line endings
    text = text.replace("\r\n", "\n")
    # Collapse multiple spaces/tabs into single space
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse excessive newlines (3+ -> 2)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf(path: Path) -> List[PageText]:
    """
    Extract text from a text-based PDF using PyMuPDF.

    Returns one PageText per page, preserving order.
    Page numbers are 1-based.
    """
    path = Path(path)
    doc = fitz.open(path)

    pages: List[PageText] = []

    for idx in range(len(doc)):
        page = doc.load_page(idx)
        raw_text = page.get_text("text") or ""
        text = _normalize_text(raw_text)

        pages.append(PageText(
            page=idx + 1,
            text=text,
            char_start=0,
            char_end=len(text)
        ))

    return pages
