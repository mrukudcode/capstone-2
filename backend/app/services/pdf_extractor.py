"""
PDF text extraction using PyMuPDF with pdfplumber fallback.

Pipeline:
    PDF
      ↓
    PyMuPDF
      ↓
    If page text is insufficient
      ↓
    pdfplumber fallback
      ↓
    Clean page text
      ↓
    Relevant-page filtering
      ↓
    Intelligent chunks
      ↓
    Groq
"""

import io
import re
from typing import List, Tuple


import fitz  # PyMuPDF
import pdfplumber


# ============================================================
# Configuration
# ============================================================

# Minimum amount of text required for PyMuPDF to be considered
# successful for a page.
MIN_PAGE_TEXT_LENGTH = 30


# Keywords which indicate that a page is likely to contain
# an actual contractual insurance-policy rule.
#
# This filtering happens LOCALLY.
# Groq is NOT called during this stage.
POLICY_RULE_PATTERNS = [
    # Waiting periods
    r"\bwaiting\s+period\b",
    r"\bpre[- ]?existing\s+disease\b",
    r"\bspecific\s+disease\s+waiting\b",
    r"\binitial\s+waiting\b",

    # Monetary / percentage limits
    r"\bsub[- ]?limit\b",
    r"\bsublimit\b",
    r"\broom\s+rent\s+(?:limit|restricted|capped)\b",
    r"\broom\s+category\s+(?:limit|restricted)\b",
    r"\bicu\s+(?:limit|charges|rent)\b",
    r"\bco[- ]?payment\b",
    r"\bcopayment\b",
    r"\bdeductible\b",
    r"\b\d+(?:\.\d+)?\s*%\s*(?:co[- ]?payment|copayment|deductible|of\s+(?:the\s+)?claim)\b",

    # Claim deadlines
    r"\bclaim\s+(?:notification|intimation)\b",
    r"\bclaim\s+(?:submission|filing)\s+(?:within|must|shall)\b",
    r"\bintimat(?:e|ion)\s+(?:within|must|shall)\b",
    r"\bwithin\s+\d+\s+(?:days?|hours?)\s+(?:of|from)\b",

    # Preauthorization
    r"\bpre[- ]?authori[sz]ation\b",
    r"\bpre[- ]?auth(?:orization)?\s+(?:is\s+)?required\b",
    r"\bcashless\s+(?:pre[- ]?authori[sz]ation|authorization)\b",

    # Exclusions / non-covered services
    r"\bpermanent\s+exclusions?\b",
    r"\b(?:general|specific)\s+exclusions?\b",
    r"\bexclusions?\s*[-:]\b",
    r"\bnot\s+covered\s+(?:under|by)\b",
    r"\bnon[- ]?covered\s+(?:treatment|procedure|expense)\b",

    # Policy validity
    r"\bpolicy\s+(?:expiry|expiration)\s+date\b",
    r"\bpolicy\s+(?:inception|commencement)\s+date\b",
    r"\bgrace\s+period\b",

    # Documentation
    r"\bdocument(?:s|ation)\s+(?:required|must\s+be\s+submitted)\b",
    r"\brequired\s+document(?:s)?\b",

    # Concrete contractual conditions
    r"\bmaximum\s+(?:amount|limit|payable)\b",
    r"\bmaximum\s+of\s+(?:rs\.?|₹|\d)\b",
    r"\blimited\s+to\s+(?:rs\.?|₹|\d)\b",
    r"\bcapped\s+at\s+(?:rs\.?|₹|\d)\b",
]
# ============================================================
# Text Cleaning
# ============================================================

def clean_page_text(text: str) -> str:
    """
    Clean extracted PDF text while preserving useful line breaks.
    """

    if not text:
        return ""

    # Remove null characters.
    text = text.replace("\x00", " ")

    cleaned_lines = []

    for line in text.splitlines():

        # Normalize spaces/tabs.
        line = re.sub(
            r"[ \t]+",
            " ",
            line
        ).strip()

        if line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


# ============================================================
# PDF Extraction
# ============================================================

def extract_text_with_pages(
    pdf_bytes: bytes
):
    """
    Extract text from a PDF page-by-page.

    Primary extractor:
        PyMuPDF

    Fallback extractor:
        pdfplumber

    If PyMuPDF produces insufficient text for a page,
    pdfplumber is used for that page.

    Returns:
        (
            full_text_with_page_markers,
            page_count
        )
    """

    # --------------------------------------------------------
    # 1. PyMuPDF extraction
    # --------------------------------------------------------

    doc = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    page_count = doc.page_count

    pages: List[Tuple[int, str]] = []

    for i, page in enumerate(
        doc,
        start=1
    ):

        try:
            text = page.get_text("text")

        except Exception:
            text = ""

        text = clean_page_text(text)

        pages.append(
            (
                i,
                text
            )
        )

    doc.close()

    # --------------------------------------------------------
    # 2. pdfplumber fallback
    # --------------------------------------------------------

    pages_needing_fallback = {
        page_number
        for page_number, text in pages
        if len(text.strip()) < MIN_PAGE_TEXT_LENGTH
    }

    if pages_needing_fallback:

        try:

            with pdfplumber.open(
                io.BytesIO(pdf_bytes)
            ) as pdf:

                for index, plumber_page in enumerate(
                    pdf.pages,
                    start=1
                ):

                    if index not in pages_needing_fallback:
                        continue

                    try:

                        fallback_text = (
                            plumber_page.extract_text()
                        )

                    except Exception:

                        fallback_text = ""

                    fallback_text = clean_page_text(
                        fallback_text
                    )

                    # Only replace PyMuPDF output if
                    # pdfplumber actually produced useful text.
                    if len(fallback_text.strip()) >= MIN_PAGE_TEXT_LENGTH:

                        pages[index - 1] = (
                            index,
                            fallback_text
                        )

        except Exception:
            # If pdfplumber itself fails, retain
            # whatever PyMuPDF extracted.
            pass

    # --------------------------------------------------------
    # 3. Build page-tagged text
    # --------------------------------------------------------

    parts = []

    for page_number, text in pages:

        parts.append(
            f"[PAGE {page_number}]\n"
            f"{text}\n"
        )

    full_text = "\n".join(parts)

    return full_text, page_count


# ============================================================
# Page Parsing
# ============================================================

def _parse_page_blocks(
    full_text: str
):
    """
    Convert page-tagged text into individual pages.

    Example:

        [PAGE 1]
        text...

        [PAGE 2]
        text...

    becomes:

        [
            (1, "text..."),
            (2, "text...")
        ]
    """

    page_splits = re.split(
        r"(?=\[PAGE \d+\])",
        full_text
    )

    pages = []

    for block in page_splits:

        block = block.strip()

        if not block:
            continue

        match = re.match(
            r"\[PAGE (\d+)\]",
            block
        )

        if not match:
            continue

        page_number = int(
            match.group(1)
        )

        page_text = re.sub(
            r"^\[PAGE \d+\]\s*",
            "",
            block,
            count=1
        ).strip()

        pages.append(
            (
                page_number,
                page_text
            )
        )

    return pages


# ============================================================
# Relevant Page Detection
# ============================================================

def score_policy_page(
    page_text: str
) -> int:
    """
    Score a page based on concrete policy-rule patterns.

    Unlike simple keyword matching, this looks for rule-bearing
    language such as durations, percentages, limits, deadlines,
    exclusions and requirements.
    """

    if not page_text:
        return 0

    score = 0

    for pattern in POLICY_RULE_PATTERNS:

        if re.search(
            pattern,
            page_text,
            flags=re.IGNORECASE
        ):
            score += 1

    return score

def find_relevant_policy_pages(
    full_text: str,
    min_score: int = 2
):
    """
    Identify pages that are likely to contain concrete
    insurance-policy rules.

    This is a LOCAL keyword-based filter.

    Groq is NOT involved.

    Returns:

        [
            (
                page_number,
                page_text,
                score
            ),
            ...
        ]
    """

    pages = _parse_page_blocks(
        full_text
    )

    relevant_pages = []

    for (
        page_number,
        page_text
    ) in pages:

        if not page_text:
            continue

        score = score_policy_page(
            page_text
        )

        if score >= min_score:

            relevant_pages.append(
                (
                    page_number,
                    page_text,
                    score
                )
            )

    return relevant_pages


# ============================================================
# Build Relevant Text
# ============================================================

def build_relevant_page_text(
    full_text: str,
    min_score: int = 2
):
    """
    Return only relevant policy pages in the same
    [PAGE N] format expected by the rule extractor.

    Non-relevant pages are removed BEFORE Groq.
    """

    relevant_pages = find_relevant_policy_pages(
        full_text,
        min_score=min_score
    )

    parts = []

    for (
        page_number,
        page_text,
        score
    ) in relevant_pages:

        parts.append(
            f"[PAGE {page_number}]\n"
            f"{page_text}\n"
        )

    return "\n".join(parts)


# ============================================================
# Intelligent Relevant-Page Chunking
# ============================================================

def chunk_relevant_policy_pages(
    full_text: str,
    pages_per_chunk: int = 2,
    min_score: int = 2
):
    """
    Find relevant pages locally and then group ONLY those
    pages into chunks for Groq.

    Example:

        Original:
            45 pages

        Relevant:
            3, 4, 8, 9, 17, 18, 24

        With pages_per_chunk=2:

            Chunk 1 -> pages 3-4
            Chunk 2 -> pages 8-9
            Chunk 3 -> pages 17-18
            Chunk 4 -> page 24

    Important:
        The chunks contain only relevant pages.

    Returns:
        List of:

        (
            chunk_text,
            start_page,
            end_page
        )
    """

    relevant_pages = find_relevant_policy_pages(
        full_text,
        min_score=min_score
    )

    chunks = []

    current = []

    for (
        page_number,
        page_text,
        score
    ) in relevant_pages:

        current.append(
            (
                page_number,
                page_text
            )
        )

        if len(current) >= pages_per_chunk:

            chunk_text = "\n".join(
                f"[PAGE {page_num}]\n"
                f"{text}\n"
                for (
                    page_num,
                    text
                ) in current
            )

            chunks.append(
                (
                    chunk_text,
                    current[0][0],
                    current[-1][0]
                )
            )

            current = []

    # Add remaining pages.
    if current:

        chunk_text = "\n".join(
            f"[PAGE {page_num}]\n"
            f"{text}\n"
            for (
                page_num,
                text
            ) in current
        )

        chunks.append(
            (
                chunk_text,
                current[0][0],
                current[-1][0]
            )
        )

    return chunks


# ============================================================
# Original Generic Chunking
# ============================================================

def chunk_by_pages(
    full_text: str,
    pages_per_chunk: int = 8
):
    """
    Split page-tagged text into chunks of N pages.

    This function is retained for compatibility with
    existing code.

    For policy rule extraction, prefer:

        chunk_relevant_policy_pages()

    Returns:
        List of:
        (
            chunk_text,
            start_page,
            end_page
        )
    """

    pages = _parse_page_blocks(
        full_text
    )

    chunks = []

    current = []
    start_page = None
    last_page = None

    for (
        page_num,
        page_text
    ) in pages:

        if start_page is None:
            start_page = page_num

        last_page = page_num

        current.append(
            (
                page_num,
                page_text
            )
        )

        if len(current) >= pages_per_chunk:

            chunk_text = "\n".join(
                f"[PAGE {num}]\n"
                f"{text}\n"
                for (
                    num,
                    text
                ) in current
            )

            chunks.append(
                (
                    chunk_text,
                    start_page,
                    last_page
                )
            )

            current = []
            start_page = None

    if current:

        chunk_text = "\n".join(
            f"[PAGE {num}]\n"
            f"{text}\n"
            for (
                num,
                text
            ) in current
        )

        chunks.append(
            (
                chunk_text,
                start_page,
                last_page
            )
        )

    return chunks