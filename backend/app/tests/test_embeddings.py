import os
import numpy as np
import pytest
from app.embeddings.embeddings import EmbeddingWrapper

os.environ["EMBEDDING_STUB"] = "true"  # Force stub for fast CI

def test_embedding_wrapper_stub():
    ew = EmbeddingWrapper()
    texts = ["hello", "world"]
    vecs = ew.embed_texts(texts)

    # Shape checks
    assert vecs.shape == (len(texts), ew.dim)
    # Dtype check
    assert vecs.dtype == np.float32
    # Optional: simple sanity check
    assert not np.all(vecs == 0)
