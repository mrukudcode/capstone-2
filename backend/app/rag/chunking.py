"""
Page-aware chunking of REAL extracted-text source documents.

Supports the page-marker formats actually present in the project:

    [PAGE 7]
    [PAGES 3-6]
    [Chapter I, para 4, ... p.4]

and:

    --- PAGE 1 ---
    --- PAGE 2 ---

The Care Supreme extracted text uses the "--- PAGE N ---" format.

No LLM or embedding call happens here.
This module only reads real extracted text and creates chunks.
"""

import os
import re
from dataclasses import dataclass, asdict
from typing import List


# ---------------------------------------------------------------------------
# DATA ROOT
# ---------------------------------------------------------------------------

_DATA_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "data",
    )
)


# ---------------------------------------------------------------------------
# DOCUMENT -> REAL EXTRACTED TEXT FILE
# ---------------------------------------------------------------------------

DOCUMENT_TEXT_FILES = {
    "STAR_ASSURE_2026_CIS":
        "raw/policies/star_health/star_assure_2026_CIS_extracted_text.txt",

    "HDFC_OPTIMA_SECURE_2026_POLICY_WORDING":
        "raw/policies/hdfc_ergo/hdfc_optima_secure_2026_policy_wording_extracted_text.txt",

    "HDFC_OPTIMA_SECURE_2026_CIS":
        "raw/policies/hdfc_ergo/hdfc_optima_secure_2026_CIS_extracted_text.txt",

    "HDFC_OPTIMA_SECURE_2021_HISTORICAL":
        "raw/policies/hdfc_ergo/hdfc_optima_secure_2021_HISTORICAL_extracted_text.txt",

    "IRDAI_MASTER_CIRCULAR_2024":
        "raw/regulatory/irdai/irdai_master_circular_2024_extracted_text.txt",

    # Care Supreme - REAL extracted PDF text
    "CARE_SUPREME_2026_POLICY":
        "processed/policies/care/care_supreme_policy_extracted_text.txt",
}


# ---------------------------------------------------------------------------
# PAGE MARKERS
# ---------------------------------------------------------------------------

# Existing formats:
#
# [PAGE 7]
# [PAGES 3-6]
# [Chapter I, para 4, ... p.4]
#
# Care format:
#
# --- PAGE 1 ---
# --- PAGE 2 ---

_BRACKET_PAGE_MARKER_RE = re.compile(
    r"^\[(.+?)\]\s*$",
    re.MULTILINE,
)

_DASH_PAGE_MARKER_RE = re.compile(
    r"^---\s*PAGE\s+(\d+)\s*---\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_SINGLE_PAGE_RE = re.compile(
    r"^PAGE\s+(\d+)$",
    re.IGNORECASE,
)

_PAGE_RANGE_RE = re.compile(
    r"^PAGES?\s+(\d+)\s*-\s*(\d+)",
    re.IGNORECASE,
)

_INLINE_PAGE_RE = re.compile(
    r"\bp\.?\s*(\d+)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# CHUNK DATA STRUCTURE
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    chunk_id: str
    policy_version_id: str
    document_id: str
    page: str
    section: str
    text: str
    provenance: str

    def to_dict(self):
        return asdict(self)


# ---------------------------------------------------------------------------
# READ DOCUMENT
# ---------------------------------------------------------------------------

def _read_document_text(document_id: str) -> str:
    if document_id not in DOCUMENT_TEXT_FILES:
        raise KeyError(
            f"Unknown document_id: {document_id}"
        )

    rel_path = DOCUMENT_TEXT_FILES[document_id]

    abs_path = os.path.join(
        _DATA_ROOT,
        rel_path,
    )

    if not os.path.exists(abs_path):
        raise FileNotFoundError(
            f"Extracted text file not found for {document_id}: "
            f"{abs_path}"
        )

    with open(
        abs_path,
        "r",
        encoding="utf-8",
    ) as f:
        return f.read()


# ---------------------------------------------------------------------------
# PARSE PAGE HEADER
# ---------------------------------------------------------------------------

def _parse_page_header(header_text: str) -> str:
    """
    Convert a page header into a real page number.

    Supported:

        PAGE 7
        PAGES 3-6
        Chapter I, para 4, p.4

    If no real page number exists, return:

        NOT_SPECIFIED_IN_SOURCE

    Never invent a page number.
    """

    header_text = header_text.strip()

    # PAGE 7
    match = _SINGLE_PAGE_RE.match(header_text)

    if match:
        return match.group(1)

    # PAGES 3-6
    match = _PAGE_RANGE_RE.match(header_text)

    if match:
        return match.group(1)

    # p.4
    match = _INLINE_PAGE_RE.search(header_text)

    if match:
        return match.group(1)

    return "NOT_SPECIFIED_IN_SOURCE"


# ---------------------------------------------------------------------------
# FIND PAGE MARKERS
# ---------------------------------------------------------------------------

def _find_page_markers(raw: str):
    """
    Find all supported page markers.

    Returns a list of tuples:

        (start_position, end_position, header_text, page_number)
    """

    markers = []

    # ---------------------------------------------------------------
    # Format 1:
    #
    # [PAGE 1]
    #
    # [PAGES 3-6]
    #
    # [Chapter I, para 4, p.4]
    # ---------------------------------------------------------------

    for match in _BRACKET_PAGE_MARKER_RE.finditer(raw):

        header_text = match.group(1).strip()

        page_number = _parse_page_header(
            header_text
        )

        markers.append(
            (
                match.start(),
                match.end(),
                header_text,
                page_number,
            )
        )

    # ---------------------------------------------------------------
    # Format 2:
    #
    # --- PAGE 1 ---
    #
    # Used by Care Supreme.
    # ---------------------------------------------------------------

    for match in _DASH_PAGE_MARKER_RE.finditer(raw):

        page_number = match.group(1)

        header_text = f"PAGE {page_number}"

        markers.append(
            (
                match.start(),
                match.end(),
                header_text,
                page_number,
            )
        )

    # ---------------------------------------------------------------
    # Sort because we have two different regexes.
    # ---------------------------------------------------------------

    markers.sort(
        key=lambda x: x[0]
    )

    return markers


# ---------------------------------------------------------------------------
# SPLIT PAGE INTO SMALLER CHUNKS
# ---------------------------------------------------------------------------

def _split_into_subchunks(
    text: str,
    target_words: int = 80,
) -> List[str]:
    """
    Split page text into focused chunks.

    We prefer paragraph/list boundaries rather than blindly slicing
    every N words.

    This helps retrieval find specific rules such as:

        waiting period
        room rent
        ICU
        PED
        exclusions
        preauthorization
        cataract
        maternity
        disease-specific waiting period
        claim documentation
        sub-limits
        co-payment

    Tiny fragments are merged into surrounding content.
    """

    # Split on:
    #
    # 1. Blank lines
    # 2. Numbered list items
    # 3. Lettered list items
    #
    units = re.split(
        r"\n\s*\n"
        r"|(?=\n\d+\.\s)"
        r"|(?=\n[A-Z]\.\s)",
        text,
    )

    units = [
        unit.strip()
        for unit in units
        if unit.strip()
    ]

    if not units:
        return [text.strip()]

    merged = []

    pending = ""

    for unit in units:

        combined = (
            f"{pending}\n{unit}".strip()
            if pending
            else unit
        )

        # Very small fragments should not become
        # standalone retrieval chunks.
        if len(combined.split()) < 20:

            pending = combined

            continue

        merged.append(
            combined
        )

        pending = ""

    # Attach remaining fragment.
    if pending:

        if merged:

            merged[-1] = (
                f"{merged[-1]}\n{pending}"
            )

        else:

            merged.append(
                pending
            )

    return (
        merged
        if merged
        else [text.strip()]
    )


# ---------------------------------------------------------------------------
# CHUNK ONE DOCUMENT
# ---------------------------------------------------------------------------

def chunk_document(
    document_id: str,
    policy_version_id: str,
    provenance: str,
) -> List[Chunk]:

    raw = _read_document_text(
        document_id
    )

    markers = _find_page_markers(
        raw
    )

    # ---------------------------------------------------------------
    # IMPORTANT:
    #
    # Some documents may not have page markers.
    #
    # We don't want to silently lose the entire document.
    #
    # Instead create one honest chunk with no fabricated page.
    # ---------------------------------------------------------------

    if not markers:

        if not raw.strip():
            return []

        subchunks = _split_into_subchunks(
            raw
        )

        chunks = []

        for index, sub_text in enumerate(
            subchunks,
            start=1,
        ):

            chunks.append(
                Chunk(
                    chunk_id=(
                        f"{document_id}-C{index:03d}"
                    ),
                    policy_version_id=(
                        policy_version_id or ""
                    ),
                    document_id=document_id,
                    page=(
                        "NOT_SPECIFIED_IN_SOURCE"
                    ),
                    section=(
                        "NO_PAGE_MARKER"
                    ),
                    text=sub_text,
                    provenance=provenance,
                )
            )

        return chunks

    # ---------------------------------------------------------------
    # Normal page-aware chunking
    # ---------------------------------------------------------------

    chunks = []

    seq = 0

    for index, marker in enumerate(
        markers
    ):

        marker_start = marker[0]
        marker_end = marker[1]
        header_text = marker[2]
        page_number = marker[3]

        # Text begins immediately after current page marker.
        start = marker_end

        # Text ends immediately before next page marker.
        if index + 1 < len(markers):

            end = markers[index + 1][0]

        else:

            end = len(raw)

        page_text = raw[
            start:end
        ].strip()

        if not page_text:
            continue

        subchunks = _split_into_subchunks(
            page_text
        )

        for sub_text in subchunks:

            seq += 1

            chunk_id = (
                f"{document_id}-C{seq:03d}"
            )

            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    policy_version_id=(
                        policy_version_id or ""
                    ),
                    document_id=document_id,
                    page=page_number,
                    section=header_text,
                    text=sub_text,
                    provenance=provenance,
                )
            )

    return chunks


# ---------------------------------------------------------------------------
# BUILD ALL DOCUMENT CHUNKS
# ---------------------------------------------------------------------------

def build_all_chunks(
    document_to_policy_version: dict,
    document_to_provenance: dict,
) -> List[Chunk]:

    """
    document_to_policy_version:

        {
            "CARE_SUPREME_2026_POLICY":
                "care_supreme_2026_v1"
        }

    document_to_provenance:

        {
            "CARE_SUPREME_2026_POLICY":
                "INSURER_DOCUMENT"
        }
    """

    all_chunks = []

    for document_id in DOCUMENT_TEXT_FILES:

        policy_version_id = (
            document_to_policy_version.get(
                document_id
            )
            or ""
        )

        provenance = (
            document_to_provenance.get(
                document_id,
                "INSURER_DOCUMENT",
            )
        )

        document_chunks = chunk_document(
            document_id=document_id,
            policy_version_id=policy_version_id,
            provenance=provenance,
        )

        all_chunks.extend(
            document_chunks
        )

    return all_chunks


# ---------------------------------------------------------------------------
# REMOVE REPEATED HEADERS FROM RETRIEVAL TEXT
# ---------------------------------------------------------------------------

_REPEATED_HEADER_RE = re.compile(
    r"^.{0,120}\|\s*UIN\s*:.{0,120}\|.{0,60}\d+\s*/\s*\d+\s*\n",
    re.IGNORECASE,
)


def retrieval_text(
    chunk_text: str,
) -> str:
    """
    Remove repeated running headers/footers before similarity scoring.

    The original Chunk.text is NOT modified.

    This only cleans the text used by TF-IDF retrieval.
    """

    return _REPEATED_HEADER_RE.sub(
        "",
        chunk_text,
        count=1,
    )
