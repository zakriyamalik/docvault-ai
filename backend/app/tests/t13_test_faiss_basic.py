def test_faiss_add_and_save_t13(tmp_path):
    import numpy as np
    from app.faiss_manager import FAISSManager

    index_path = str(tmp_path / "t13_test.faiss")

    manager = FAISSManager()
    manager.create_index(index_path, dim=4)

    # FAISSManager expects a NumPy array with ndim == 2
    vectors = np.array([
        [0.1, 0.2, 0.3, 0.4],
        [0.4, 0.3, 0.2, 0.1]
    ], dtype="float32")

    ids = manager.add_vectors(vectors)

    assert len(ids) == 2

    manager.save_index(index_path)
