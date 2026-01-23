from fastapi import UploadFile
from app.storage import save_upload
from app.repository import create_document_row

def manual_test_upload():
    # Open local file
    with open("app/tests/fixtures/sample.pdf", "rb") as f:
        upload_file = UploadFile(filename="sample.pdf", file=f)
        
        # Save file
        saved_path, size_bytes = save_upload(upload_file)
        print("Saved file:", saved_path, "Size:", size_bytes)
        
        # Insert DB row
        document_id = create_document_row(
            filename=saved_path.name,
            size_bytes=size_bytes,
            status="queued"
        )
        print("Created document row:", document_id)

if __name__ == "__main__":
    manual_test_upload()
