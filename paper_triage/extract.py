"""PDF text extraction helpers."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pypdf import PdfReader

LOGGER = logging.getLogger(__name__)


def extract_text(
    pdf_path: Path,
    max_pages: int = 3,
    max_chars: int = 4000,
) -> str:
    """Extract text from the first few pages of a PDF."""

    if max_pages <= 0:
        raise ValueError("max_pages must be positive")

    text_chunks = []
    try:
        reader = PdfReader(str(pdf_path))
        pages_to_read = min(len(reader.pages), max_pages)
        for index in range(pages_to_read):
            try:
                page = reader.pages[index]
                chunk = page.extract_text() or ""
                text_chunks.append(chunk)
                if sum(len(chunk) for chunk in text_chunks) >= max_chars:
                    break
            except Exception as page_err:  # pragma: no cover - defensive logging
                LOGGER.warning("Failed to extract page %s from %s: %s", index, pdf_path, page_err)
                continue
    except Exception as exc:
        LOGGER.error("Unable to read PDF %s: %s", pdf_path, exc)
        return ""

    text = "\n".join(text_chunks)
    if len(text) > max_chars:
        return text[:max_chars]
    return text


__all__ = ["extract_text"]
