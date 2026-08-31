"""
PDF text extraction using PyMuPDF (fitz).

Extracts page-tagged text matching the same [PAGE N] convention
used throughout this project's manually-extracted policy documents.
"""

import re
import fitz  # pymupdf


def extract_text_with_pages(pdf_bytes: bytes):
    """
    Extract text from a PDF.

    Returns:
        (full_text_with_page_markers, page_count)
    """

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    page_count = doc.page_count
    parts = []

    for i, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()

        parts.append(
            f"[PAGE {i}]\n"
            f"{text}\n"
        )

    doc.close()

    full_text = "\n".join(parts)

    return full_text, page_count


def chunk_by_pages(full_text: str, pages_per_chunk: int = 8):
    """
    Split page-tagged text into chunks of N pages.

    Returns:
        List of:
        (chunk_text, start_page, end_page)
    """

    page_splits = re.split(
        r"(?=\[PAGE \d+\])",
        full_text
    )

    page_splits = [
        p for p in page_splits
        if p.strip()
    ]

    chunks = []

    current = []
    start_page = None
    last_page = None

    for block in page_splits:

        match = re.match(
            r"\[PAGE (\d+)\]",
            block
        )

        page_num = int(match.group(1)) if match else None

        if start_page is None:
            start_page = page_num

        last_page = page_num

        current.append(block)

        if len(current) >= pages_per_chunk:

            chunks.append(
                (
                    "".join(current),
                    start_page,
                    last_page
                )
            )

            current = []
            start_page = None

    if current:
        chunks.append(
            (
                "".join(current),
                start_page,
                last_page
            )
        )

    return chunks