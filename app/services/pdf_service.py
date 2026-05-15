import logging
from dataclasses import dataclass
from pathlib import Path

import fitz

from app.utils.text import clean_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PageText:
    page: int
    text: str


class PDFService:
    def extract_pages(self, file_path: Path) -> list[PageText]:
        try:
            pages: list[PageText] = []
            with fitz.open(file_path) as doc:
                for index, page in enumerate(doc, start=1):
                    text = clean_text(page.get_text("text"))
                    if text:
                        pages.append(PageText(page=index, text=text))
            return pages
        except Exception:
            logger.exception("Failed to extract text from PDF: %s", file_path)
            raise ValueError("Unable to read this PDF. It may be encrypted, scanned, or corrupted.")
