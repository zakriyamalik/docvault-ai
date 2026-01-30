def test_ocr_fallback_reads_image_only_t13():
    from app.parser.pdf_extractor import extract_pdf_with_ocr

    pages = extract_pdf_with_ocr("/app/app/tests/fixtures/image_only.pdf")

    assert isinstance(pages, list)
    assert any(
        (p.get("text") if isinstance(p, dict) else getattr(p, "text", ""))
        for p in pages
    )

