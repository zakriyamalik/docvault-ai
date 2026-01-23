from pathlib import Path
from typing import List

from .base import PageText


def extract_txt(path: Path) -> List[PageText]:
    """
    Read a text file, decode it, and return a single PageText (page=1).
    UTF-8 is tried first, then ISO-8859-1 as fallback.
    """
    path = Path(path)
    raw = path.read_bytes()

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("iso-8859-1")

    char_start = 0
    char_end = len(text)

    return [PageText(page=1, text=text, char_start=char_start, char_end=char_end)]
