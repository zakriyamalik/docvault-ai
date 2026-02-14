# backend/app/retrieval/retriever.py
from typing import List, Dict, Any, Optional
import json
from app.db.postgres_conn import get_db
from app.embeddings.embeddings import EmbeddingWrapper
from app.faiss_manager import FAISSManager


def retrieve_relevant_chunks(
    query: str,
    top_k: int = 5,
    faiss_index_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant chunks for a query using FAISS similarity search.
    """
    # Get query embedding
    ew = EmbeddingWrapper()
    query_vector = ew.embed_texts([query])[0]
    
    # Load FAISS index
    faiss_mgr = FAISSManager()
    if faiss_index_path:
        faiss_mgr.load_index(faiss_index_path)
    else:
        # Use default path
        import os
        default_path = os.getenv("FAISS_INDEX_PATH", "/data/faiss/default.faiss")
        faiss_mgr.load_index(default_path)
    
    # Search FAISS
    distances, indices = faiss_mgr.search(query_vector.reshape(1, -1), top_k)
    
    # Get chunk details from PostgreSQL
    results = []
    with get_db() as conn:
        with conn.cursor() as cur:
            for idx, distance in zip(indices[0], distances[0]):
                if idx < 0:
                    continue
                
                # Look up chunk by vector_id
                cur.execute(
                    "SELECT c.id, c.document_id, c.text, c.chunk_index, d.filename "
                    "FROM chunks c "
                    "JOIN faiss_index_map fim ON c.id = fim.chunk_id "
                    "JOIN documents d ON c.document_id = d.id "
                    "WHERE fim.vector_id = %s",
                    (str(idx),),
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
    """
    Get full text context from a document (for summarization).
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT text FROM chunks WHERE document_id = %s ORDER BY chunk_index LIMIT %s",
                (doc_id, max_chunks),
            )
            texts = [row[0] for row in cur.fetchall()]
    
    return "\n\n".join(texts)
