# test_chunk_insert.py
from app.db.sqlite_conn import get_db
from uuid import uuid4
from app.chunker.tokenizer_wrapper import get_tokenizer
from app.chunker.chunker import chunk_pages, persist_chunks_to_db

# 1️⃣ Create a new document row
document_id = str(uuid4())
with get_db() as conn:
    conn.execute(
        """
        INSERT INTO documents (id, filename, size_bytes, status, source_type)
        VALUES (?, ?, ?, ?, ?)
        """,
        (document_id, "testfile.pdf", 1234, "processing", "upload")
    )
    conn.commit()
print("Created document:", document_id)

# 2️⃣ Prepare pages for chunking
# Reduce repetition to avoid >512 token warning
text_repeat = "Hello world. " * 50  # ~200 tokens
pages = [{"page": 1, "text": text_repeat}]

# 3️⃣ Initialize tokenizer
tok = get_tokenizer()  # must be fast tokenizer

# 4️⃣ Generate chunks
chunks = chunk_pages(document_id, pages, tok)
print(f"Chunks generated: {len(chunks)}")
for i, c in enumerate(chunks[:3]):
    print(f"{i}: token_count={c['token_count']}, preview={c['preview'][:30]}")

# 5️⃣ Persist chunks to DB
persist_chunks_to_db(chunks)
print("Chunks persisted to DB.")

# 6️⃣ Verify in DB
with get_db() as conn:
    row = conn.execute(
        "SELECT COUNT(*) as c FROM chunks WHERE document_id=?",
        (document_id,)
    ).fetchone()
print(f"Chunks in DB for document {document_id}: {row['c']}")
