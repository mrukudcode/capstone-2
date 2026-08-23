# Dataset Guide — Where to Look

Quick pointers for inspecting this project's data directly in an editor
(VS Code or otherwise). No code execution required for any of these.

## To inspect the real, extracted policy rules
Open:
```
data/structured/policy_rule_candidates.csv
```
Each row is one clause, with `source_document`, `source_page`, and
`source_text` columns showing exactly where it came from.

## To inspect the real source documents (extracted text)
Open:
```
data/raw/policies/star_health/star_assure_2026_CIS_extracted_text.txt
data/raw/policies/hdfc_ergo/hdfc_optima_secure_2026_policy_wording_extracted_text.txt
data/raw/policies/hdfc_ergo/hdfc_optima_secure_2026_CIS_extracted_text.txt
data/raw/policies/hdfc_ergo/hdfc_optima_secure_2021_HISTORICAL_extracted_text.txt
data/raw/regulatory/irdai/irdai_master_circular_2024_extracted_text.txt
```
Each file starts with a metadata header (source URL, UIN, fetch method)
and uses `[PAGE N]` markers matching the source document's own printed
pagination.

## To inspect which document backs which policy version
Open:
```
data/structured/source_documents.csv
data/structured/policy_inventory.csv
```

## To inspect the HDFC UIN conflict in detail
Open:
```
docs/HDFC_ERGO_UIN_REVIEW.md
```

## To inspect synthetic test claims
Open:
```
data/synthetic/claims.json
```
Each entry has `"claim_provenance": "SYNTHETIC"`, a `"derived_from_rule"`
pointing at the real rule it exercises, and an `"expected_severity"`.

## To inspect the dataset's own self-validation
Open:
```
data/structured/dataset_validation_report.json
```
Regenerate it with `python3 scripts/validate_dataset.py`.

## To inspect the deterministic rule engine
Open:
```
backend/app/rules/engine.py         (orchestrator)
backend/app/rules/waiting_period.py
backend/app/rules/room_rent.py
backend/app/rules/sublimit.py
backend/app/rules/copay.py
backend/app/rules/deductible.py
backend/app/rules/deadline.py
backend/app/rules/preauth.py
backend/app/rules/documentation.py
backend/app/rules/exclusion.py
backend/app/rules/eligibility.py
backend/app/rules/policy_status.py
backend/app/services/financial_calculator.py
```
Full behavior documented in `docs/rule_engine.md`.

## To inspect the tests
Open:
```
backend/tests/test_rule_engine.py
```
Run with `cd backend && python3 -m pytest tests/ -v`.

## Data flow

```
REAL POLICY PDF
      |
      v
PDF EXTRACTION (web_fetch text extraction --
  raw PDF bytes not retrievable in this environment,
  see docs/limitations.md)
      |
      v
PAGE-TAGGED TEXT
  (data/raw/**/*_extracted_text.txt, [PAGE N] markers)
      |
      v
STRUCTURED POLICY RULES
  (data/structured/policy_rule_candidates.csv,
   review_status = PENDING / NEEDS_REVIEW / APPROVED / REJECTED)
      |
      v
DATABASE
  (backend/claim_validator.db, seeded by
   backend/app/database/seed.py -- no fabricated rows)
      |
      v
DETERMINISTIC RULE ENGINE
  (backend/app/rules/engine.py -- filters to
   claim.policy_version_id ONLY, excludes NEEDS_REVIEW rules
   from automatic evaluation)
      |
      v
CLAIM VALIDATION
  (PASS / WARNING / PARTIAL_DEDUCTION / FAIL per rule,
   SUBMISSION_READY / HUMAN_REVIEW_NEEDED / FIX_BEFORE_SUBMISSION overall)
```
