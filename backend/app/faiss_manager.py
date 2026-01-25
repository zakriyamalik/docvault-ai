from __future__ import annotations

import os
import uuid
import pickle
from typing import List

import numpy as np
import faiss
from filelock import FileLock


class FAISSManager:
    """
    FAISS index manager with:
    - IndexFlatIP (inner product)
    - UUID-based vector IDs
    - Persistent storage
    - Single-writer safety via file lock (on save only)

    IMPORTANT:
    Only ONE process (worker) is allowed to write to the index.
    Readers must load a saved snapshot.
    """

    def __init__(self):
        self.index: faiss.Index | None = None
        self.dim: int | None = None
        self.vector_ids: List[str] = []

    # -------------------------
    # Index lifecycle
    # -------------------------

    def create_index(self, index_path: str, dim: int) -> None:
        """
        Create a new FAISS index and reset ID mapping.
        """
        self.dim = int(dim)
        self.index = faiss.IndexFlatIP(self.dim)
        self.vector_ids = []

        os.makedirs(os.path.dirname(index_path), exist_ok=True)

    def load_index(self, index_path: str) -> None:
        """
        Load FAISS index and UUID mapping from disk.
        """
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"FAISS index not found: {index_path}")

        ids_path = index_path + ".ids.pkl"
        if not os.path.exists(ids_path):
            raise FileNotFoundError(f"FAISS ID mapping not found: {ids_path}")

        self.index = faiss.read_index(index_path)

        with open(ids_path, "rb") as f:
            self.vector_ids = pickle.load(f)

        self.dim = self.index.d

    # -------------------------
    # Vector operations
    # -------------------------

    def add_vectors(self, vectors: np.ndarray) -> List[str]:
        """
        Add vectors to the FAISS index and return UUIDs.
        """
        if self.index is None:
            raise RuntimeError("FAISS index is not initialized")

        if vectors.ndim != 2:
            raise ValueError("Vectors must be a 2D numpy array")

        if vectors.shape[1] != self.dim:
            raise ValueError(
                f"Vector dim mismatch: expected {self.dim}, got {vectors.shape[1]}"
            )

        vectors = vectors.astype(np.float32)

        new_ids = [str(uuid.uuid4()) for _ in range(len(vectors))]

        self.index.add(vectors)
        self.vector_ids.extend(new_ids)

        return new_ids

    # -------------------------
    # Persistence (SINGLE WRITER)
    # -------------------------

    def save_index(self, index_path: str) -> None:
        """
        Persist FAISS index and UUID mapping to disk.

        LOCKING:
        - Uses a file lock to prevent concurrent writes
        - Only the worker process should call this
        """
        if self.index is None:
            raise RuntimeError("FAISS index is not initialized")

        os.makedirs(os.path.dirname(index_path), exist_ok=True)

        lock_path = index_path + ".lock"
        ids_path = index_path + ".ids.pkl"

        with FileLock(lock_path):
            faiss.write_index(self.index, index_path)

            with open(ids_path, "wb") as f:
                pickle.dump(self.vector_ids, f)

    # -------------------------
    # Introspection
    # -------------------------

    def get_index_count(self) -> int:
        """
        Return number of vectors currently in the index.
        """
        if self.index is None:
            return 0
        return self.index.ntotal
