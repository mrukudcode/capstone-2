# Evaluation Report (Real Numbers Only)

Generated from this session's actual runs — no fabricated metrics.

## Dataset
- Insurers: 2 (Star Health and Allied Insurance Co Ltd; HDFC ERGO General Insurance Company Limited)
- Products: 2 (Star Health Assure Insurance Policy; my:Optima Secure)
- Policy versions: 4 (`star_assure_2026_v1`, `hdfc_optima_secure_2026_v1`,
  `hdfc_optima_secure_2026_v1_CIS_UIN`, `hdfc_optima_secure_2021_v1`)
- Source documents: 5, all `hash_type=EXTRACTED_TEXT` (see docs/limitations.md
  for why `ORIGINAL_FILE` hashes weren't achievable this session)
- Rule candidates: 59 total
  - Insurer-document rules: 49
  - Regulatory (IRDAI) rules: 10
  - `review_status=NEEDS_REVIEW`: 17 (all HDFC 2026, quarantined pending
    UIN conflict resolution)
  - `review_status=PENDING`: 42 (all currently evaluable/active)
  - `review_status=APPROVED`: 0 (nothing has been human-approved yet — by
    design, no rule auto-approves itself)

## Dataset validation (`scripts/validate_dataset.py`)
- ERRORS: **0**
- WARNINGS: **5** (all `hash_type=EXTRACTED_TEXT`, documented environment
  limitation, not a data-quality defect)

## Rule engine coverage
- Rule categories with at least one implemented, tested evaluator: **12**
  of the 16 categories in the CSV's controlled vocabulary that have any
  active rule instance, plus 2 (`POLICY_INACTIVE`/`POLICY_EXPIRED`)
  covered only via clearly-labelled derived logic, plus 1
  (`ELIGIBILITY_FAILURE`) honestly left unimplemented because zero rule
  rows of that type exist in the dataset.

## Automated tests
- `backend/tests/test_rule_engine.py`: **18 tests, 18 passed, 0 failed**
  (`pytest -q` — full log available by re-running; not reproduced here to
  avoid restating output that can go stale).
- Boundary tests included for: initial waiting period, specified-disease
  waiting period, room rent, sub-limit, co-payment, deductible
  opt-in/opt-out, claim filing deadline (both Star's 15-day and HDFC
  2021's 30-day rule, proving version-specific values are respected),
  notification deadline, preauth lead time, documentation/KYC threshold,
  exclusion keyword-overlap (confirmed capped at WARNING), full
  policy-version isolation, and HDFC 2026 NEEDS_REVIEW quarantine.
- One real bug was found and fixed during this process (`sublimit.py`
  percentage-parsing bug — see `docs/rule_engine.md` "Bugs found and
  fixed" section).

## Synthetic claim consistency check
- `scripts/generate_synthetic_claims.py` produced **28 synthetic claims**
  in `data/synthetic/claims.json`, every one derived from a real
  `candidate_id` and its actual extracted value (no invented thresholds).
- `scripts/check_synthetic_claims.py` ran all 28 through the real engine:
  **28 passed, 0 failed** (after fixing one synthetic-case data error —
  see below).
- One synthetic-case authoring error was found and fixed: the original
  "notified 25 hours after admission" case could not be represented,
  because `Claim.admission_date`/`notification_date` are `Date` columns
  without time-of-day, so a 24h vs 25h distinction cannot be stored at
  day granularity. Replaced with a 48-hour-gap case that the schema can
  actually represent. Documented in `docs/rule_engine.md` limitation #1.

## What this evaluation does NOT claim
- No claim-outcome/insurer-approval accuracy percentage is reported,
  because no real insurer adjudication ground truth exists for this
  project (as instructed). "Correctness" here means: rule evaluation
  logic matches the values and conditions actually printed in the source
  documents, boundary arithmetic is exact, and policy-version isolation
  holds — not that the system predicts what an insurer will decide.

## API integration
- `test_api_health`, `test_api_full_flow`, `test_api_policies_endpoints`
  all pass against the live FastAPI app via `TestClient` (in-process, no
  separate server process needed for the test suite).

## Not yet evaluated (because not yet built)
RAG citation correctness, FHIR export correctness, frontend rendering —
see `docs/limitations.md`.
