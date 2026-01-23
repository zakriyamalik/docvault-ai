import re
from pathlib import Path

from app.parser import extract_txt, extract_docx, extract_pdf, PageText

# FIXTURES: refer to repo's tests/fixtures directory
FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures"


def _assert_page(page: PageText):
    # Offsets contract
    assert page.char_start == 0
    assert page.char_end == len(page.text)
    assert page.slice() == page.text

    # Page number
    assert isinstance(page.page, int)
    assert page.page >= 1

    # Content sanity: non-empty and contains at least one alphanumeric character
    assert len(page.text) > 0
    assert re.search(r"[A-Za-z0-9]", page.text), "page text contains no alphanumeric characters"


def test_txt_extractor():
    path = FIXTURES / "sample.txt"
    pages = extract_txt(path)

    assert len(pages) == 1
    page = pages[0]
    _assert_page(page)


def test_docx_extractor():
    path = FIXTURES / "sample.docx"
    pages = extract_docx(path)

    assert len(pages) >= 1
    page = pages[0]
    _assert_page(page)


def test_pdf_extractor():
    path = FIXTURES / "sample.pdf"
    pages = extract_pdf(path)

    assert len(pages) >= 1
    first = pages[0]
    _assert_page(first)
