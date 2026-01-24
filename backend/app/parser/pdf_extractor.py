from pathlib import Path
from typing import List, Dict
import re
from io import BytesIO

import fitz  # PyMuPDF

from .base import PageText
from .ocr import ocr_image_page


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


def _render_page_to_png_bytes(page: fitz.Page, dpi: int = 150) -> bytes:
    """
    Render a PyMuPDF page to PNG image bytes.
    dpi controls resolution — higher dpi gives better OCR at cost of CPU/RAM.
    """
    # use matrix for dpi scaling
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    # get PNG bytes
    return pix.tobytes(output="png")


def extract_pdf_with_ocr(path: Path, ocr_threshold: int = 50, dpi: int = 150) -> List[Dict]:
    """
    Extract text from a PDF with OCR fallback.

    For each page:
      - Extract native text
      - If native text length (after strip) < ocr_threshold:
          - Render the page to image bytes (PNG)
          - Call ocr_image_page(image_bytes)
          - Merge native + OCR text (native first, then OCR)
          - Mark ocr_used = True
      - Else:
          - Keep native text, ocr_used = False

    Returns:
      A list of page metadata dicts:
        {
          "page": int,           # 1-based page number
          "text": str,           # merged text (native + ocr if used)
          "ocr_used": bool
        }

    Notes:
      - This function deliberately returns page metadata dicts (not PageText)
        so we can include the `ocr_used` flag. Keep extract_pdf() unchanged
        for backwards compatibility.
    """
    path = Path(path)
    doc = fitz.open(path)

    pages_meta: List[Dict] = []

    for idx in range(len(doc)):
        page = doc.load_page(idx)
        raw_text = page.get_text("text") or ""
        native_text = _normalize_text(raw_text)

        ocr_used = False
        final_text = native_text

        if len(native_text.strip()) < ocr_threshold:
            # Low-text page: render and OCR
            try:
                png_bytes = _render_page_to_png_bytes(page, dpi=dpi)
                ocr_text = ocr_image_page(png_bytes) or ""
                ocr_text = _normalize_text(ocr_text)
                # Merge native + OCR (native first so searchable text preserves native tokens)
                if native_text:
                    final_text = native_text + "\n" + ocr_text if ocr_text else native_text
                else:
                    final_text = ocr_text
                ocr_used = True
            except Exception as e:
                # In case OCR fails, keep native_text and mark ocr_used False.
                # We keep failure silent here but could log if logging is in place.
                final_text = native_text
                ocr_used = False

        pages_meta.append({
            "page": idx + 1,
            "text": final_text,
            "ocr_used": ocr_used
        })

    return pages_meta
