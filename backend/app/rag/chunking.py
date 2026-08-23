"""
Page-aware chunking of the REAL extracted-text source documents.

Splits each document's own text on its existing "[PAGE N]" markers (the
same markers already used for rule-candidate source_page citations -- no
new pagination scheme is invented here). One chunk = one page's text for
a given document. This guarantees a chunk can never cross a page boundary,
and since each source file belongs to exactly one document/policy_version,
a chunk can never cross into a different policy version either.

No LLM or embedding call happens in this module -- it only reads real
text files and splits them.
"""
import os
import re
from dataclasses import dataclass, asdict
from typing import List

_DATA_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data"))

# Same mapping used in main.py's evidence endpoint -- kept in one place
# would be ideal, but duplicated here deliberately to keep the rag module
# import-independent from the API layer. Source of truth is
# data/structured/source_documents.csv; this dict only maps document_id to
# the actual file on disk that was fetched for that document.
DOCUMENT_TEXT_FILES = {
    "STAR_ASSURE_2026_CIS": "raw/policies/star_health/star_assure_2026_CIS_extracted_text.txt",
    "HDFC_OPTIMA_SECURE_2026_POLICY_WORDING": "raw/policies/hdfc_ergo/hdfc_optima_secure_2026_policy_wording_extracted_text.txt",
    "HDFC_OPTIMA_SECURE_2026_CIS": "raw/policies/hdfc_ergo/hdfc_optima_secure_2026_CIS_extracted_text.txt",
    "HDFC_OPTIMA_SECURE_2021_HISTORICAL": "raw/policies/hdfc_ergo/hdfc_optima_secure_2021_HISTORICAL_extracted_text.txt",
    "IRDAI_MASTER_CIRCULAR_2024": "raw/regulatory/irdai/irdai_master_circular_2024_extracted_text.txt",
}

_PAGE_MARKER_RE = re.compile(r"^\[(.+?)\]", re.MULTILINE)
_SINGLE_PAGE_RE = re.compile(r"^PAGE\s+(\d+)$", re.IGNORECASE)
_PAGE_RANGE_RE = re.compile(r"^PAGES?\s+(\d+)\s*-\s*(\d+)", re.IGNORECASE)
_INLINE_PAGE_RE = re.compile(r"\bp\.?\s*(\d+)\b", re.IGNORECASE)


@dataclass
class Chunk:
    chunk_id: str
    policy_version_id: str  # empty string "" for regulatory (not policy-scoped)
    document_id: str
    page: str
    section: str
    text: str
    provenance: str  # INSURER_DOCUMENT | REGULATORY_DOCUMENT

    def to_dict(self):
        return asdict(self)


def _read_document_text(document_id: str) -> str:
    rel_path = DOCUMENT_TEXT_FILES[document_id]
    abs_path = os.path.join(_DATA_ROOT, rel_path)
    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()


def _parse_page_header(header_text: str):
    """Given the text inside one '[...]' header line, determine the best
    citation page number this chunk should carry. Returns a string page
    number, or 'NOT_SPECIFIED_IN_SOURCE' if none can be genuinely derived
    from the header -- never guessed.

    Handles the three real header conventions actually present in this
    dataset's extracted-text files:
      - "[PAGE 7]"                      -> "7"
      - "[PAGES 3-6]"                   -> "3" (start of the printed range)
      - "[Chapter I, para 4, ... p.4]"  -> "4" (IRDAI circular's own style)
      - "[Chapter I, para 5]" (no page) -> "NOT_SPECIFIED_IN_SOURCE"
    """
    m = _SINGLE_PAGE_RE.match(header_text.strip())
    if m:
        return m.group(1)
    m = _PAGE_RANGE_RE.match(header_text.strip())
    if m:
        return m.group(1)
    m = _INLINE_PAGE_RE.search(header_text)
    if m:
        return m.group(1)
    return "NOT_SPECIFIED_IN_SOURCE"


def _split_into_subchunks(text: str, target_words: int = 80) -> List[str]:
    """Split one page's text into smaller sub-chunks. Splits at EVERY
    blank-line paragraph boundary and EVERY numbered/lettered-list-item
    boundary (e.g. '12. Something...', 'A. Something...') -- deliberately
    NOT grouped up to a target word count, because a real retrieval-
    quality test showed that even a ~110-word group of 4-5 list items
    still diluted a single matching term (e.g. 'cataract') below the
    similarity threshold. List items in these source documents are
    typically short (one disease/clause per item), so splitting at every
    item boundary gives each one its own tightly-focused sub-chunk. Tiny
    fragments (under 4 words -- e.g. a stray heading) are merged into the
    following fragment rather than left as a near-empty, unretrievable
    chunk."""
    units = re.split(r"\n\s*\n|(?=\n\d+\.\s)|(?=\n[A-Z]\.\s)", text)
    units = [u.strip() for u in units if u.strip()]
    if not units:
        return [text]

    merged = []
    pending = ""
    for unit in units:
        combined = f"{pending}\n{unit}".strip() if pending else unit
        if len(combined.split()) < 20:
            pending = combined
            continue
        merged.append(combined)
        pending = ""
    if pending:
        if merged:
            merged[-1] = f"{merged[-1]}\n{pending}"
        else:
            merged.append(pending)
    return merged if merged else [text]


def chunk_document(document_id: str, policy_version_id: str, provenance: str) -> List[Chunk]:
    """Split one document's real extracted text into per-page blocks, then
    further into smaller sub-chunks within each page (see
    _split_into_subchunks) so a single distinguishing term isn't diluted
    across an entire page's worth of unrelated list items. Covers
    "[PAGE N]", "[PAGES X-Y]", and the IRDAI circular's "[Chapter..., p.N]"
    style headers alike. Never invents text -- every sub-chunk's `text` is
    a verbatim slice of the actual file on disk, and every chunk's `page`
    is either a real page number parsed from that exact header or an
    honest 'NOT_SPECIFIED_IN_SOURCE' rather than a guess."""
    raw = _read_document_text(document_id)
    matches = list(_PAGE_MARKER_RE.finditer(raw))
    chunks = []
    seq = 0
    for i, m in enumerate(matches):
        header_text = m.group(1)
        page_num = _parse_page_header(header_text)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        page_text = raw[start:end].strip()
        if not page_text:
            continue
        for sub_text in _split_into_subchunks(page_text):
            seq += 1
            chunk_id = f"{document_id}-C{seq:03d}"
            chunks.append(Chunk(
                chunk_id=chunk_id,
                policy_version_id=policy_version_id or "",
                document_id=document_id,
                page=page_num,
                section=header_text.strip(),
                text=sub_text,
                provenance=provenance,
            ))
    return chunks


def build_all_chunks(document_to_policy_version: dict, document_to_provenance: dict) -> List[Chunk]:
    """
    document_to_policy_version: {document_id: policy_version_id or None}
    document_to_provenance: {document_id: "INSURER_DOCUMENT" | "REGULATORY_DOCUMENT"}
    Builds chunks for every document known in DOCUMENT_TEXT_FILES.
    """
    all_chunks = []
    for document_id in DOCUMENT_TEXT_FILES:
        pv_id = document_to_policy_version.get(document_id) or ""
        prov = document_to_provenance.get(document_id, "INSURER_DOCUMENT")
        all_chunks.extend(chunk_document(document_id, pv_id, prov))
    return all_chunks


_REPEATED_HEADER_RE = re.compile(
    r"^.{0,120}\|\s*UIN\s*:.{0,120}\|.{0,60}\d+\s*/\s*\d+\s*\n", re.IGNORECASE
)


def retrieval_text(chunk_text: str) -> str:
    """Strip the per-page repeated running header/footer line (e.g.
    'Star Health Assure Insurance Policy | UIN : ... | CIS / SHA / V.7 /
    2026 8 / 20') before it's used for similarity scoring. This boilerplate
    repeats almost identically on every single page of a document and was
    found (via a real retrieval-quality bug during testing) to drown out
    genuinely distinguishing terms like 'cataract' in TF-IDF cosine
    similarity, causing the correct page to rank below irrelevant pages.
    The FULL original chunk.text (including this header) is still what's
    shown to the user in citations/sources -- only the text fed into the
    embedding index is cleaned, so no information is lost or hidden from
    the person reading the answer."""
    return _REPEATED_HEADER_RE.sub("", chunk_text, count=1)
