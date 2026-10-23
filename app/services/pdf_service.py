"""Service for reading and splitting PDF pages."""

from io import BytesIO
from typing import List, Union
from pypdf import PdfReader
from app.schemas.models import PageData


class PDFService:
    @staticmethod
    def extract_pages(pdf_source: Union[str, bytes]) -> List[PageData]:
        """Extracts text per page from file path or raw bytes."""
        if isinstance(pdf_source, bytes):
            reader = PdfReader(BytesIO(pdf_source))
        else:
            reader = PdfReader(pdf_source)

        pages: List[PageData] = []
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            # Clean up text
            cleaned_text = "\n".join(
                line.strip() for line in text.splitlines() if line.strip()
            )
            pages.append(
                PageData(
                    page_number=idx + 1,
                    text=cleaned_text,
                    char_count=len(cleaned_text),
                )
            )
        return pages

    @staticmethod
    def get_pages_by_numbers(all_pages: List[PageData], page_numbers: List[int]) -> List[PageData]:
        """Returns only the specified pages (1-indexed)."""
        target_set = set(page_numbers)
        return [p for p in all_pages if p.page_number in target_set]

    @staticmethod
    def format_pages_for_prompt(pages: List[PageData]) -> str:
        """Formats a list of pages into a clear prompt string."""
        if not pages:
            return "No pages provided."
        parts = []
        for p in pages:
            parts.append(f"--- PAGE {p.page_number} ---\n{p.text}")
        return "\n\n".join(parts)
