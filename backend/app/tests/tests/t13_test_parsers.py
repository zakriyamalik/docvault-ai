def test_pdf_parser_basic_t13():
    from app.parser.pdf_extractor import extract_pdf

    pages = extract_pdf("/app/app/tests/fixtures/sample.pdf")

    assert isinstance(pages, list)
    assert any(getattr(p, "text", "") for p in pages)

