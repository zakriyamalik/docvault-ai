from dataclasses import dataclass

@dataclass
class PageText:
    """
    A page of extracted document text.

    page: 1-based page number
    text: full text content of the page
    char_start: 0-based inclusive start offset (usually 0)
    char_end: exclusive end offset (len(text))
    """
    page: int
    text: str
    char_start: int
    char_end: int

    def slice(self) -> str:
        return self.text[self.char_start:self.char_end]
