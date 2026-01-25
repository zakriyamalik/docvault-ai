"""
Diagnostic: FAISS Manager Step-3

Validates:
- Index creation (IndexFlatIP)
- Adding vectors
- Persistence to disk
- Reload from disk
- Vector count integrity
"""

import os
import shutil
import numpy as np

from app.faiss_manager import FAISSManager

FAISS_DIR = "/data/faiss"
INDEX_PATH = os.path.join(FAISS_DIR, "index.faiss")


def main():
    # Clean slate
    os.makedirs(FAISS_DIR, exist_ok=True)

    for fname in os.listdir(FAISS_DIR):
     fpath = os.path.join(FAISS_DIR, fname)
     if os.path.isfile(fpath):
        os.remove(fpath)


    dim = 384
    num_vectors = 10

    # -------------------------
    # Step 1: Create index
    # -------------------------
    manager = FAISSManager()
    manager.create_index(INDEX_PATH, dim)

    assert manager.get_index_count() == 0, "Index should be empty after creation"

    # -------------------------
    # Step 2: Add vectors
    # -------------------------
    vectors = np.random.rand(num_vectors, dim).astype(np.float32)
    ids = manager.add_vectors(vectors)

    assert len(ids) == num_vectors, "Returned UUID count mismatch"
    assert manager.get_index_count() == num_vectors, "Index count mismatch after add"

    # -------------------------
    # Step 3: Save index (LOCKED)
    # -------------------------
    manager.save_index(INDEX_PATH)

    assert os.path.exists(INDEX_PATH), "FAISS index file not saved"
    assert os.path.exists(INDEX_PATH + ".ids.pkl"), "ID mapping file not saved"

    # -------------------------
    # Step 4: Reload index
    # -------------------------
    manager2 = FAISSManager()
    manager2.load_index(INDEX_PATH)

    assert manager2.get_index_count() == num_vectors, "Index count mismatch after reload"
    assert len(manager2.vector_ids) == num_vectors, "UUID mapping mismatch after reload"

    print("✅ FAISS Manager Step-3 diagnostic PASSED")
    print(f"Index path: {INDEX_PATH}")
    print(f"Vector count: {manager2.get_index_count()}")


if __name__ == "__main__":
    main()
