"""PDF text extraction utilities."""

from __future__ import annotations

from io import BytesIO
from typing import BinaryIO

from pypdf import PdfReader


def extract_text_from_pdf(file: BinaryIO | bytes) -> str:
    """Extract normalized text from an uploaded PDF file."""
    source = BytesIO(file) if isinstance(file, bytes) else file
    if hasattr(source, "seek"):
        source.seek(0)

    reader = PdfReader(source)
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n".join(page for page in pages if page).strip()
