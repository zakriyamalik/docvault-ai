from pathlib import Path
from app.parser.pdf_extractor import extract_pdf_with_ocr

FIXTURES = Path(__file__).parent / "fixtures"

def test_pdf_ocr_fallback():
    path = FIXTURES / "ocr_only.pdf"
    pages = extract_pdf_with_ocr(path)

    assert len(pages) >= 1
    page = pages[0]

    assert page.get("ocr_used", False) is True
    assert len(page.get("text", "").strip()) > 0
    assert "OCR" in page.get("text", "").upper()
