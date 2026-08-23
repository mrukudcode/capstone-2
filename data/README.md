# `data/` — Directory Guide

## `data/raw/`
Extracted **plain text** of real source documents (policy wordings, CIS
summaries, the IRDAI Master Circular), with page markers preserved where
the source PDF's own printed pagination was visible.

**Important honest caveat:** these are *extracted text*, not the original
PDF bytes. This session's tools could not retrieve raw PDF bytes (see
`docs/limitations.md`), so `data/raw/` here contains `.txt` files, not
`.pdf` files. Each file's own header records the exact source URL it was
fetched from and the UIN/version printed in the document body.

- `data/raw/policies/star_health/` — Star Health Assure Insurance Policy
- `data/raw/policies/hdfc_ergo/` — HDFC ERGO my:Optima Secure (current + 2021 historical)
- `data/raw/regulatory/irdai/` — IRDAI Master Circular on Health Insurance Business, 29-May-2024

## `data/processed/`
Intermediate/working extraction artifacts. Currently contains one file
(`star_assure_2026_CIS_raw.txt`) that predates the finalized page-marked
version in `data/raw/`; kept for traceability, not treated as the
canonical source.

## `data/structured/` — the core dataset, CSV/JSON
- **`source_documents.csv`** — one row per real source document: URL, UIN,
  hash, hash_type, page_count, status. This is the top of the provenance
  chain.
- **`policy_inventory.csv`** — one row per distinct `policy_version_id`:
  insurer, product, UIN, which document(s) back it, and any UIN conflict
  flag.
- **`policy_rule_candidates.csv`** — the 59 extracted rules. Every row
  traces to a `source_document`, `source_page`, and `source_text`, and
  carries a `review_status` (`PENDING`/`APPROVED`/`REJECTED`/`NEEDS_REVIEW`).
  This is the file to open if you want to see exactly what a rule says and
  where it came from.
- **`dataset_validation_report.json`** — machine-generated, real counts
  and any errors/warnings, produced by `scripts/validate_dataset.py`. Not
  hand-written.

**Not yet split out** (documented gap, not silently missing):
`regulatory_rules.csv` and `policy_versions.csv` don't exist as separate
files — that data currently lives inside `policy_rule_candidates.csv`
(rows with `provenance=REGULATORY_DOCUMENT`) and `policy_inventory.csv`
respectively.

## `data/synthetic/`
- **`claims.json`** — 28 **synthetic** test claims, each one explicitly
  tagged `"claim_provenance": "SYNTHETIC"` and
  `"expected_result_provenance": "DERIVED_FROM_REAL_RULE"`, and each one
  traceable via `"derived_from_rule"` back to a real row in
  `policy_rule_candidates.csv`. These are NOT real patients or real
  insurer decisions — see `docs/dataset_documentation.md` for the full
  provenance distinction.

## How to inspect this data as a mentor (no code required)
1. Open `data/structured/policy_rule_candidates.csv` in VS Code's built-in
   CSV viewer or any spreadsheet tool — every row shows the rule, its
   value, and its exact source page/text.
2. Open `data/structured/source_documents.csv` to see where every document
   came from and its hash/provenance status.
3. Open `data/raw/policies/star_health/star_assure_2026_CIS_extracted_text.txt`
   to read the actual extracted policy text with `[PAGE N]` markers.
4. Open `data/synthetic/claims.json` to see the synthetic test claims and
   which real rule each one exercises.
5. Open `data/structured/dataset_validation_report.json` for the
   machine-verified real counts (0 errors, 5 documented warnings as of
   the last run).
