from __future__ import annotations

import os
import uuid
import pickle
from typing import List, Tuple, Optional

import numpy as np
import faiss
from filelock import FileLock


class FAISSManager:
    """
    FAISS manager - returns uuids_batch, distances_batch
    """
    def __init__(self):
        self.index: faiss.Index | None = None
        self.dim: int | None = None
        self.vector_ids: List[str] = []

    def create_index(self, index_path: str, dim: int) -> None:
        self.dim = int(dim)
        self.index = faiss.IndexFlatIP(self.dim)
        self.vector_ids = []
        os.makedirs(os.path.dirname(index_path), exist_ok=True)

    def load_index(self, index_path: str) -> None:
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"FAISS index not found: {index_path}")
        ids_path = index_path + ".ids.pkl"
        if not os.path.exists(ids_path):
            raise FileNotFoundError(f"FAISS ID mapping not found: {ids_path}")
        self.index = faiss.read_index(index_path)
        with open(ids_path, "rb") as f:
            self.vector_ids = pickle.load(f)
        self.dim = self.index.d

    def add_vectors(self, vectors: np.ndarray) -> List[str]:
        if self.index is None:
            raise RuntimeError("FAISS index is not initialized")
        if vectors.ndim != 2:
            raise ValueError("Vectors must be a 2D numpy array")
        if vectors.shape[1] != self.dim:
            raise ValueError(f"Vector dim mismatch: expected {self.dim}, got {vectors.shape[1]}")
        vectors = vectors.astype(np.float32)
        new_ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
        self.index.add(vectors)
        self.vector_ids.extend(new_ids)
        return new_ids

    def search(self, query_vector: np.ndarray, k: int = 5) -> Tuple[List[List[Optional[str]]], List[List[float]]]:
        """
        Returns:
          - uuids_batch: List[List[Optional[str]]] shape (batch, k)
          - distances_list: List[List[float]] shape (batch, k)
        """
        if self.index is None:
            raise RuntimeError("FAISS index is not loaded")

        q = np.asarray(query_vector, dtype=np.float32)
        if q.ndim == 1:
            q = q.reshape(1, -1)

        if q.shape[1] != self.dim:
            raise ValueError(f"Query vector dimension mismatch: expected {self.dim}, got {q.shape[1]}")

        distances_np, indices_np = self.index.search(q, k)
        distances_list: List[List[float]] = distances_np.tolist()
        indices_list: List[List[int]] = indices_np.tolist()

        uuids_batch: List[List[Optional[str]]] = []
        for row in indices_list:
            row_uuids: List[Optional[str]] = []
            for idx in row:
                if idx is None:
                    row_uuids.append(None)
                elif isinstance(idx, (int, np.integer)) and idx >= 0 and idx < len(self.vector_ids):
                    row_uuids.append(self.vector_ids[int(idx)])
                else:
                    row_uuids.append(None)
            uuids_batch.append(row_uuids)

        # pad if needed
        for i in range(len(distances_list)):
            if len(distances_list[i]) < k:
                distances_list[i].extend([float("inf")] * (k - len(distances_list[i])))
            if len(uuids_batch[i]) < k:
                uuids_batch[i].extend([None] * (k - len(uuids_batch[i])))

        return uuids_batch, distances_list

    def save_index(self, index_path: str) -> None:
        if self.index is None:
            raise RuntimeError("FAISS index is not initialized")
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        lock_path = index_path + ".lock"
        ids_path = index_path + ".ids.pkl"
        with FileLock(lock_path):
            faiss.write_index(self.index, index_path)
            with open(ids_path, "wb") as f:
                pickle.dump(self.vector_ids, f)

    def get_index_count(self) -> int:
        if self.index is None:
            return 0
        return self.index.ntotal
