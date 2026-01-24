from io import BytesIO
from PIL import Image
import pytesseract


def ocr_image_page(image_bytes: bytes) -> str:
    """
    Perform OCR on a single page image.

    Args:
        image_bytes: Raw image bytes (e.g., PNG) rendered from a PDF page.

    Returns:
        Extracted text as a string (English).
    """
    image = Image.open(BytesIO(image_bytes))
    text = pytesseract.image_to_string(image, lang="eng")
    return text.strip()
