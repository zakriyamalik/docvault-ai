from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from app.db.postgres_conn import get_db
from app.embeddings.embeddings import EmbeddingWrapper
from app.faiss_manager import FAISSManager
import logging
import os

logger = logging.getLogger(__name__)

@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None
    score: float = 0.0
    @property
    def chunk_index(self) -> Optional[int]:
        if self.metadata and isinstance(self.metadata, dict):
            return self.metadata.get("chunk_index")
        return None
    @property
    def preview(self) -> str:
        return (self.content or "")[:400]

def retrieve_relevant_chunks(
    query: str,
    top_k: int = 5,
    faiss_index_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    ew = EmbeddingWrapper()
    query_vector = ew.embed_texts([query])[0]

    faiss_mgr = FAISSManager()
    target_path = faiss_index_path or os.getenv("FAISS_INDEX_PATH", "/data/faiss/default.faiss")
    logger.info("[DEBUG BACKEND] Target file exists: %s", os.path.exists(target_path))
    faiss_mgr.load_index(target_path)

    uuids_batch, distances_batch = faiss_mgr.search(query_vector.reshape(1, -1), top_k)

    # Normalize
    if isinstance(uuids_batch, list) and uuids_batch and not isinstance(uuids_batch[0], list):
        uuids_batch = [uuids_batch]
    if isinstance(distances_batch, list) and distances_batch and not isinstance(distances_batch[0], list):
        distances_batch = [distances_batch]

    results: List[Dict[str, Any]] = []
    with get_db() as conn:
        with conn.cursor() as cur:
            for uuid_val, distance in zip(uuids_batch[0], distances_batch[0]):
                if uuid_val is None:
                    continue

                cur.execute(
                    "SELECT c.id, c.document_id, c.text, c.chunk_index, d.filename "
                    "FROM chunks c "
                    "JOIN faiss_index_map fim ON c.id = fim.chunk_id "
                    "JOIN documents d ON c.document_id = d.id "
                    "WHERE fim.vector_id = %s",
                    (str(uuid_val),),
                )
                row = cur.fetchone()
                if row:
                    results.append({
                        "chunk_id": row[0],
                        "document_id": row[1],
                        "text": row[2],
                        "chunk_index": row[3],
                        "filename": row[4],
                        "score": float(distance),
                    })
    return results

def get_document_context(doc_id: str, max_chunks: int = 10) -> str:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT text FROM chunks WHERE document_id = %s ORDER BY chunk_index LIMIT %s",
                (doc_id, max_chunks),
            )
            texts = [row[0] for row in cur.fetchall()]
    return "\n\n".join(texts)

def retrieve(query: str, top_k: int = 5) -> List[Chunk]:
    rows = retrieve_relevant_chunks(query, top_k)
    out: List[Chunk] = []
    for r in rows:
        out.append(Chunk(
            chunk_id=r["chunk_id"],
            document_id=r["document_id"],
            content=r["text"],
            score=r.get("score", 0.0),
            metadata={"chunk_index": r.get("chunk_index"), "filename": r.get("filename")}
        ))
    return out
