def test_embeddings_stub_or_model_t13():
    from app.embeddings.embeddings import EmbeddingWrapper

    ew = EmbeddingWrapper()
    vectors = ew.embed_texts(["hello world", "another text"])

    assert isinstance(vectors, list)
    assert len(vectors) == 2
