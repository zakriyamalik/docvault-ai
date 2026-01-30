def test_chunker_creates_chunks_t13():
    from app.chunker.chunker import chunk_pages
    from app.chunker.tokenizer_wrapper import get_tokenizer

    pages = [
        {
            "page": 1,
            "text": "hello world " * 50,
            "metadata": {}
        }
    ]

    tokenizer = get_tokenizer()
    chunks = chunk_pages("test-doc-t13", pages, tokenizer)

    assert isinstance(chunks, list)
    assert len(chunks) >= 1
