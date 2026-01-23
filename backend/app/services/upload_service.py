from fastapi import UploadFile
from app.storage import save_upload
from app.repository import create_document_row

def handle_upload(file: UploadFile):
    # Step 1: Save file to disk
    saved_path, size_bytes = save_upload(file)

    # Step 2: Create DB row
    document_id = create_document_row(
        filename=saved_path.name,
        size_bytes=size_bytes,
        status="queued"
    )

    return {
        "document_id": document_id,
        "file_path": str(saved_path),
        "size_bytes": size_bytes
    }
