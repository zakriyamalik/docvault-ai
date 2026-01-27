# backend/app/tools/rebuild_faiss_from_chunks.py
"""
Rebuild FAISS index from chunks table (DB is source of truth).

Usage:
  python -m app.tools.rebuild_faiss_from_chunks
  python -m app.tools.rebuild_faiss_from_chunks --document-id <uuid>
  python -m app.tools.rebuild_faiss_from_chunks --force

Guarantees:
- DB-first ordering
- Idempotent
- Safe to rerun
"""

import os
import argparse
import logging
from typing import List, Tuple

from app.db.sqlite_conn import get_db
from app.embeddings.embeddings import EmbeddingWrapper
from app.faiss_manager import FAISSManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FAISS_INDEX_NAME = os.getenv("FAISS_INDEX_NAME", "default")
FAISS_INDEX_PATH = os.getenv(
    "FAISS_INDEX_PATH",
    f"/data/faiss/{FAISS_INDEX_NAME}.faiss",
)

BATCH_SIZE_EMBED = int(os.getenv("EMBED_BATCH", "64"))


def load_chunks(document_id: str | None) -> List[dict]:
    query = """
        SELECT id, document_id, text
        FROM chunks
        WHERE text IS NOT NULL AND trim(text) != ''
    """
    params = []

    if document_id:
        query += " AND document_id = ?"
        params.append(document_id)

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(r) for r in rows]


def clear_existing_mappings(document_id: str | None):
    with get_db() as conn:
        cur = conn.cursor()

        if document_id:
            logger.info("Clearing faiss_index_map for document %s", document_id)
            cur.execute(
                """
                DELETE FROM faiss_index_map
                WHERE chunk_id IN (
                    SELECT id FROM chunks WHERE document_id = ?
                )
                """,
                (document_id,),
            )
            cur.execute(
                "UPDATE chunks SET vector_id = NULL WHERE document_id = ?",
                (document_id,),
            )
        else:
            logger.info("Clearing entire faiss_index_map")
            cur.execute("DELETE FROM faiss_index_map")
            cur.execute("UPDATE chunks SET vector_id = NULL")

        conn.commit()


def rebuild(document_id: str | None, force: bool):
    logger.info("Starting FAISS rebuild (document_id=%s, force=%s)", document_id, force)

    chunks = load_chunks(document_id)
    if not chunks:
        logger.warning("No chunks found — nothing to rebuild")
        return

    logger.info("Loaded %d chunks from DB", len(chunks))

    # Clear mappings first (DB-first safety)
    clear_existing_mappings(document_id)

    ew = EmbeddingWrapper()
    faiss_mgr = FAISSManager()

    if force or not os.path.exists(FAISS_INDEX_PATH):
        logger.info("Creating new FAISS index at %s", FAISS_INDEX_PATH)
        faiss_mgr.create_index(FAISS_INDEX_PATH, dim=ew.dim)
    else:
        logger.info("Loading existing FAISS index at %s", FAISS_INDEX_PATH)
        faiss_mgr.load_index(FAISS_INDEX_PATH)

    vector_map: List[Tuple[str, str]] = []

    for i in range(0, len(chunks), BATCH_SIZE_EMBED):
        batch = chunks[i : i + BATCH_SIZE_EMBED]
        texts = [c["text"] for c in batch]

        vectors = ew.embed_texts(texts)
        vector_ids = faiss_mgr.add_vectors(vectors)

        for vid, c in zip(vector_ids, batch):
            vector_map.append((vid, c["id"]))

    faiss_mgr.save_index(FAISS_INDEX_PATH)
    logger.info("FAISS rebuilt with %d vectors", len(vector_map))

    created_at = __import__("datetime").datetime.utcnow().isoformat()

    with get_db() as conn:
        cur = conn.cursor()

        cur.executemany(
            """
            INSERT INTO faiss_index_map
            (vector_id, chunk_id, index_name, dim, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (vid, cid, FAISS_INDEX_NAME, ew.dim, created_at)
                for vid, cid in vector_map
            ],
        )

        cur.executemany(
            "UPDATE chunks SET vector_id = ? WHERE id = ?",
            [(vid, cid) for vid, cid in vector_map],
        )

        conn.commit()

    logger.info("Rebuild completed successfully")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--document-id", help="Rebuild only for this document")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete and recreate FAISS index",
    )

    args = parser.parse_args()
    rebuild(args.document_id, args.force)


if __name__ == "__main__":
    main()
