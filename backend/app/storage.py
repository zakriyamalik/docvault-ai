from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile
import mimetypes

# Directory where files are saved
UPLOAD_DIR = Path("/data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

# Maximum file size in bytes (50 MB)
MAX_SIZE_BYTES = 50 * 1024 * 1024

def save_upload(file: UploadFile) -> tuple[Path, int]:
    """
    Save uploaded file securely with streaming to prevent memory spikes.

    Args:
        file (UploadFile): FastAPI uploaded file

    Returns:
        Tuple[Path, int]: (saved file path, size in bytes)
    """
    # Validate extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type not allowed: {ext}")

    # Optional: validate MIME type
    mime_type, _ = mimetypes.guess_type(file.filename)
    if mime_type is None:
        raise ValueError("Cannot determine MIME type of file")

    # Generate secure filename
    safe_filename = f"{uuid4().hex}_{Path(file.filename).name}"
    dest_path = UPLOAD_DIR / safe_filename

    # Stream file in chunks
    size = 0
    with dest_path.open("wb") as f:
        for chunk in iter(lambda: file.file.read(1024 * 1024), b""):  # 1 MB chunks
            size += len(chunk)
            if size > MAX_SIZE_BYTES:
                dest_path.unlink(missing_ok=True)  # delete partial file
                raise ValueError("File exceeds 50MB limit")
            f.write(chunk)

    return dest_path, size
