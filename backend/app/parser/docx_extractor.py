from pathlib import Path
from typing import List

from docx import Document

from .base import PageText


def extract_docx(path: Path) -> List[PageText]:
    """
    Extract text from a DOCX file.

    If explicit page breaks are present, split into multiple pages.
    Otherwise, return a single PageText with page=1.
    """
    path = Path(path)
    doc = Document(path)

    pages = [""]
    current_page = 0

    for para in doc.paragraphs:
        pages[current_page] += para.text + "\n"

        # Detect explicit page breaks in runs (best-effort)
        for run in para.runs:
            # Page break is represented in XML as w:br with type='page'
            if run._element.xpath(".//w:br[@w:type='page']"):
                pages.append("")
                current_page += 1

    results: List[PageText] = []
    for i, text in enumerate(pages, start=1):
        text = text.rstrip("\n")
        results.append(PageText(
            page=i,
            text=text,
            char_start=0,
            char_end=len(text)
        ))

    return results
