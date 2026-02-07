import logging
import os
import pickle  # ADD THIS
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)
MAX_PREVIEW_LEN = 300

DEFAULT_FAISS_INDEX = "/data/faiss/default.faiss"


@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    chunk_index: Optional[int]
    preview: str
    score: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "preview": self.preview,
            "score": self.score,
        }


def _truncate(text: str, max_len: int = MAX_PREVIEW_LEN) -> str:
    if not text:
        return ""
    return text[:max_len].rstrip() + "..." if len(text) > max_len else text


def _normalize_scores(raw_scores: List[float], invert: bool = False) -> List[float]:
    if not raw_scores:
        return []
    min_s, max_s = min(raw_scores), max(raw_scores)
    if max_s == min_s:
        return [0.5] * len(raw_scores)
    normalized = [(s - min_s) / (max_s - min_s) for s in raw_scores]
    return [1.0 - s for s in normalized] if invert else normalized


def _get_db():
    """Get DB connection."""
    from app.db.sqlite_conn import get_db
    return get_db()


def _get_embedding_wrapper():
    """Lazy init embedding wrapper."""
    from app.embeddings.embeddings import EmbeddingWrapper
    return EmbeddingWrapper()


def _get_faiss_manager():
    """Lazy init FAISS manager."""
    from app.faiss_manager import FAISSManager
    return FAISSManager()


def _get_faiss_index_path() -> str:
    """Get FAISS index path."""
    return os.getenv("FAISS_INDEX_PATH", DEFAULT_FAISS_INDEX)


def _db_fallback_retrieve(query: str, top_k: int) -> Tuple[List[Chunk], float]:
    """Fallback: return most recent chunks from DB."""
    logger.warning("Retriever: using DB fallback mode")
    
    try:
        with _get_db() as conn:
            rows = conn.execute(
                """
                SELECT id, document_id, chunk_index, text, created_at
                FROM chunks
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (top_k,),
            ).fetchall()
            
            chunks = []
            for row in rows:
                chunks.append(Chunk(
                    chunk_id=str(row["id"]),
                    document_id=str(row["document_id"]) if row["document_id"] else "unknown",
                    chunk_index=row["chunk_index"],
                    preview=_truncate(row["text"]),
                    score=0.5,
                ))
            
            logger.info("DB fallback returned %d chunks", len(chunks))
            return chunks, 0.5 if chunks else 0.0
            
    except Exception as e:
        logger.error("DB fallback failed: %s", e)
        return [], 0.0


def _faiss_retrieve(query: str, top_k: int) -> Tuple[List[Chunk], float]:
    """FAISS-based retrieval with proper UUID mapping."""
    try:
        ew = _get_embedding_wrapper()
        faiss_mgr = _get_faiss_manager()
        index_path = _get_faiss_index_path()
        
        if not os.path.exists(index_path):
            logger.warning("FAISS index not found at %s", index_path)
            raise FileNotFoundError(f"FAISS index missing: {index_path}")
        
        faiss_mgr.load_index(index_path)
        
        query_vec = ew.embed_texts([query])
        import numpy as np
        query_vec = np.array(query_vec).astype('float32')
        
        distances, faiss_indices = faiss_mgr.index.search(query_vec, top_k)
        
        faiss_positions = faiss_indices[0].tolist() if hasattr(faiss_indices, 'tolist') else list(faiss_indices[0])
        distances = distances[0].tolist() if hasattr(distances, 'tolist') else list(distances[0])
        
        valid_results = [(int(pos), float(dist)) for pos, dist in zip(faiss_positions, distances) if pos >= 0]
        if not valid_results:
            raise ValueError("No valid FAISS results")
        
        faiss_positions, raw_scores = zip(*valid_results)
        
        # FIX: Load position->UUID mapping from .ids.pkl file
        ids_pkl_path = index_path + '.ids.pkl'
        with open(ids_pkl_path, 'rb') as f:
            id_list = pickle.load(f)
        position_to_vector = {i: uuid for i, uuid in enumerate(id_list)}
        
        with _get_db() as conn:
            vector_rows = conn.execute(
                "SELECT vector_id, chunk_id FROM faiss_index_map"
            ).fetchall()
            vector_to_chunk = {row[0]: row[1] for row in vector_rows}
            
            chunk_ids = []
            valid_positions = []
            valid_scores = []
            
            for pos, score in zip(faiss_positions, raw_scores):
                vector_id = position_to_vector.get(pos)
                if not vector_id:
                    logger.warning("No vector_id found for position %s", pos)
                    continue
                
                chunk_id = vector_to_chunk.get(vector_id)
                if not chunk_id:
                    logger.warning("No chunk_id found for vector_id %s", vector_id)
                    continue
                
                chunk_ids.append(chunk_id)
                valid_positions.append(pos)
                valid_scores.append(score)
            
            if not chunk_ids:
                raise ValueError("No valid chunk mappings found")
            
            placeholders = ','.join('?' * len(chunk_ids))
            rows = conn.execute(
                f"""
                SELECT id, document_id, chunk_index, text
                FROM chunks
                WHERE id IN ({placeholders})
                """,
                chunk_ids,
            ).fetchall()
            
            row_map = {str(row["id"]): row for row in rows}
            
            chunks_raw = []
            scores_ordered = []
            
            for pos, chunk_id, score in zip(valid_positions, chunk_ids, valid_scores):
                row = row_map.get(chunk_id)
                if not row:
                    logger.warning("Chunk %s not found in DB", chunk_id)
                    continue
                
                chunks_raw.append({
                    "chunk_id": str(row["id"]),
                    "document_id": str(row["document_id"]) if row["document_id"] else "unknown",
                    "chunk_index": row["chunk_index"],
                    "preview": _truncate(row["text"]),
                })
                scores_ordered.append(score)
            
            if not chunks_raw:
                raise ValueError("No chunks could be fetched from DB")
            
            norm_scores = _normalize_scores(scores_ordered, invert=True)
            chunks = [Chunk(**cr, score=ns) for cr, ns in zip(chunks_raw, norm_scores)]
            
            logger.info("FAISS retrieved %d chunks", len(chunks))
            return chunks, max(norm_scores) if norm_scores else 0.0
            
    except Exception as e:
        logger.warning("FAISS failed: %s", e)
        return _db_fallback_retrieve(query, top_k)


def retrieve(query: str, top_k: int = 5) -> Tuple[List[Chunk], float]:
    """Public API: retrieve top-k chunks."""
    query = query.strip() if query else ""
    if not query:
        return [], 0.0
    
    top_k = max(1, min(top_k, 100))
    
    try:
        return _faiss_retrieve(query, top_k)
    except Exception as e:
        logger.exception("FAISS failed, using DB fallback: %s", e)
        return _db_fallback_retrieve(query, top_k)