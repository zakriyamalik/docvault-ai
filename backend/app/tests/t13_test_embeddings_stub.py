def test_embeddings_stub_or_model_t13():
    from app.embeddings.embeddings import EmbeddingWrapper

    ew = EmbeddingWrapper()
    vectors = ew.embed_texts(["hello world", "another text"])

    # EmbeddingWrapper may return a numpy array or list depending on implementation.
    # Coerce numpy arrays to list for a deterministic assertion.
    try:
        vecs_list = vectors.tolist()
    except Exception:
        vecs_list = list(vectors) if not isinstance(vectors, list) else vectors

    assert isinstance(vecs_list, list)
    assert len(vecs_list) == 2
