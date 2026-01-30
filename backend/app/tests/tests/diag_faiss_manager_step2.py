import os
import shutil
import numpy as np

from app.faiss_manager import FAISSManager


INDEX_PATH = "/data/faiss/test_index.faiss"


def main():
    # Clean previous test artifacts
    if os.path.exists("/data/faiss"):
        shutil.rmtree("/data/faiss")

    os.makedirs("/data/faiss", exist_ok=True)

    # -------------------------
    # Create index
    # -------------------------
    fm = FAISSManager()
    fm.create_index(INDEX_PATH, dim=384)

    assert fm.get_index_count() == 0, "Index should start empty"

    # -------------------------
    # Add vectors
    # -------------------------
    vectors = np.random.rand(5, 384).astype("float32")
    ids = fm.add_vectors(vectors)

    assert len(ids) == 5, "Should return 5 UUIDs"
    assert fm.get_index_count() == 5, "Index count should be 5"

    # -------------------------
    # Save index
    # -------------------------
    fm.save_index(INDEX_PATH)

    assert os.path.exists(INDEX_PATH), "FAISS index file not saved"
    assert os.path.exists(INDEX_PATH + ".ids.pkl"), "ID mapping not saved"

    # -------------------------
    # Reload index
    # -------------------------
    fm2 = FAISSManager()
    fm2.load_index(INDEX_PATH)

    assert fm2.get_index_count() == 5, "Reloaded index count mismatch"
    assert len(fm2.vector_ids) == 5, "Reloaded UUID mapping mismatch"

    print("✅ STEP-2 FAISS MANAGER DIAGNOSTIC PASSED")


if __name__ == "__main__":
    main()
