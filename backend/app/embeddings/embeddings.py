"""
Embedding wrapper for local sentence-transformers models with CI-friendly stub.

- Loads model once per process
- Batches embedding calls
- Optional stub mode via EMBEDDING_STUB=true for fast CI
"""

from __future__ import annotations

import os
from typing import List

import numpy as np


class EmbeddingWrapper:
    """Local embedding wrapper with batching and optional stub mode."""

    DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
    DEFAULT_DIM = 384

    def __init__(self, batch_size: int = 64, normalize: bool = False):
        self.batch_size = int(batch_size)
        self.normalize = bool(normalize)

        self._stub = os.getenv("EMBEDDING_STUB", "false").lower() == "true"
        self._device = os.getenv("EMBEDDING_DEVICE", "cpu")

        self._model = None
        self.dim = self.DEFAULT_DIM

        if not self._stub:
            # Lazy import to keep stub mode fast/light
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.DEFAULT_MODEL_NAME, device=self._device)
            self._model.max_seq_length = 512
            # Resolve dimension from model to avoid assumptions
            try:
                self.dim = int(self._model.get_sentence_embedding_dimension())
            except Exception:
                self.dim = self.DEFAULT_DIM

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Embed a list of texts into a 2D numpy array (n_texts, dim).

        Returns float32 vectors. Always returns a 2D array.
        """
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)

        # Stub path: deterministic, fast, CI-safe
        if self._stub:
            rng = np.random.default_rng(seed=42)
            arr = rng.standard_normal((len(texts), self.dim)).astype(np.float32)
            if self.normalize:
                arr = self._l2_normalize(arr)
            return arr

        # Real model path with batching
        all_vecs: List[np.ndarray] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            vecs = self._model.encode(
                batch,
                convert_to_numpy=True,
                normalize_embeddings=False,
                show_progress_bar=False,
            )
            vecs = np.asarray(vecs, dtype=np.float32)
            all_vecs.append(vecs)

        out = np.vstack(all_vecs) if all_vecs else np.zeros((0, self.dim), dtype=np.float32)
        if self.normalize:
            out = self._l2_normalize(out)
        return out

    @staticmethod
    def _l2_normalize(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
        norm = np.linalg.norm(x, axis=1, keepdims=True)
        return x / np.maximum(norm, eps)
