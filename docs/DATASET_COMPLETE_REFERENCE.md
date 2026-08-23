# DATASET DEEP-DIVE — Complete Reference

This document explains ONLY the dataset (`data/` folder). It does not
cover the backend, frontend, or rule engine code — just what data exists,
where, in what shape, and what every field means. Read this top to
bottom once, and you'll understand the dataset better than most people
who just skim files.

---

## PART 1 — THE BIG PICTURE

Everything in `data/` exists to support one chain:

```
REAL POLICY DOCUMENT (a PDF published by an insurer or IRDAI)
        ↓
EXTRACTED TEXT (the document's words, kept in page order)
        ↓
STRUCTURED RULE (one specific clause, pulled out and tagged)
        ↓
SYNTHETIC TEST CLAIM (a made-up claim designed to test one specific rule)
        ↓
EXPECTED RESULT (what the rule SHOULD say for that test claim)
```

Three provenance labels are used consistently across every file:

| Label | Meaning | Where you'll see it |
|---|---|---|
| **REAL** | Came from an actual published document | `source_documents.csv`, the `.txt` files, the `source_text` column in rules |
| **DERIVED** | Extracted/computed from real material | the rule rows themselves; expected test results |
| **SYNTHETIC** | Made up for testing purposes only | every entry in `claims.json` |

**Golden rule to remember:** the *rules* are real. The *test claims* are fake. Never confuse the two.

---

## PART 2 — DIRECTORY STRUCTURE, FILE BY FILE

```
data/
├── raw/                          ← extracted text of real documents
│   ├── policies/
│   │   ├── star_health/
│   │   │   └── star_assure_2026_CIS_extracted_text.txt
│   │   └── hdfc_ergo/
│   │       ├── hdfc_optima_secure_2026_policy_wording_extracted_text.txt
│   │       ├── hdfc_optima_secure_2026_CIS_extracted_text.txt
│   │       ├── hdfc_optima_secure_2026_policy_wording_meta.txt
│   │       └── hdfc_optima_secure_2021_HISTORICAL_extracted_text.txt
│   └── regulatory/
│       └── irdai/
│           └── irdai_master_circular_2024_extracted_text.txt
│
├── processed/                    ← intermediate/legacy extraction artifacts
│   ├── policies/star_health/star_assure_2026_CIS_raw.txt   (superseded draft)
│   ├── pages/                    (not yet implemented — see Part 6)
│   └── chunks/                   (not yet implemented — see Part 6)
│
├── structured/                   ← THE CORE — everything as clean tables
│   ├── source_documents.csv          (5 rows — one per real document)
│   ├── policy_inventory.csv          (4 rows — one per policy version)
│   ├── policy_rule_candidates.csv    (59 rows — one per extracted rule)
│   └── dataset_validation_report.json (machine-generated health check)
│
└── synthetic/
    └── claims.json                (28 test claims, NOT real)
```

---

## PART 3 — THE FIVE REAL SOURCE DOCUMENTS

These are the actual insurer/regulator publications everything else is
built from. Full detail lives in `source_documents.csv`; here's the plain
explanation of each:

### 1. `STAR_ASSURE_2026_CIS`
- **What it is:** The Customer Information Sheet (CIS) — a plain-language
  summary IRDAI requires alongside every policy — for **Star Health
  Assure Insurance Policy**, the current 2026 version.
- **UIN (unique policy identifier):** `SHAHLIP26048V032526`
- **Pages:** 20
- **Where it came from:** Star Health's own website CDN, linked from
  their official downloads page.

### 2. `HDFC_OPTIMA_SECURE_2026_POLICY_WORDING`
- **What it is:** The full, detailed **Policy Wording** document (the
  actual contract, not just a summary) for HDFC ERGO's **my:Optima
  Secure** product, current 2026 version.
- **UIN printed in this document:** `HDFHLIP26058V082526`
- **Pages:** 60 total in the source (we only extracted the first ~42 —
  see Part 6, "known gaps")
- **Where it came from:** HDFC ERGO's official website.

### 3. `HDFC_OPTIMA_SECURE_2026_CIS`
- **What it is:** The Customer Information Sheet for the SAME product
  as #2, but — and this is important — **it prints a different UIN**:
  `HDFHLIP25041V062425`.
- **Pages:** 12
- **This is the "UIN conflict"** — see Part 5 below, it's the single
  most interesting/important quirk in this dataset.

### 4. `HDFC_OPTIMA_SECURE_2021_HISTORICAL`
- **What it is:** An older, historical (2021) version of the SAME HDFC
  product, combining both the CIS and full Policy Wording in one PDF.
- **UIN:** `HDFHLIP21016V012122`
- **Pages:** 24
- **Why it matters:** This lets us prove "policy-version isolation" —
  a 2021 claim must never accidentally get checked against 2026 rules,
  and vice versa. The rules from this document are deliberately kept
  completely separate.

### 5. `IRDAI_MASTER_CIRCULAR_2024`
- **What it is:** NOT an insurer document — this is a **government
  regulatory circular** from IRDAI (India's insurance regulator),
  titled "Master Circular on Health Insurance Business," dated
  29-May-2024, reference `IRDAI/HLT/CIR/PRO/84/5/2024`.
- **Pages:** 17
- **Why it's separate:** Its rules apply to ALL insurers generally
  (e.g. "cashless pre-authorization must be decided within 1 hour"),
  not to one specific product — so it's tagged with a different
  provenance (`REGULATORY_DOCUMENT` instead of `INSURER_DOCUMENT`).

**Every single one of these five files has an honest limitation flag:**
`hash_type = EXTRACTED_TEXT` (not `ORIGINAL_FILE`). This means the
fingerprint (hash) we computed is of the extracted text, not the raw PDF
bytes — because the tooling available couldn't fetch raw PDF bytes
directly. This is documented, not hidden, in every row of
`source_documents.csv`.

---

## PART 4 — THE 59 STRUCTURED RULES, CATEGORY BY CATEGORY

Every rule lives in `policy_rule_candidates.csv`, one row per rule. Here
is every column and what it means:

| Column | Meaning |
|---|---|
| `candidate_id` | Unique ID, e.g. `SA26-002` (SA26 = Star Assure 2026, 002 = second rule found) or `HDFC21-007` (HDFC 2021 historical) or `IRDAI-003` (regulatory) |
| `insurer` / `product` / `uin` / `policy_version` | Which policy this rule belongs to |
| `rule_type` | The category (see table below) |
| `rule_name` | Short human label |
| `condition` | The situation this rule applies under |
| `value` / `unit` | The actual number and its unit, e.g. `24` / `MONTHS` |
| `applies_to` | What kind of claim/treatment this rule covers |
| `exception` | Any carve-out stated in the source |
| `source_document` | Which of the 5 documents this came from |
| `source_page` | Exact page number |
| `source_text` | The exact quoted sentence(s) from the document |
| `review_status` | `PENDING` (extracted, not yet human-approved), `NEEDS_REVIEW` (flagged as unreliable — see Part 5), `APPROVED`, or `REJECTED` |
| `provenance` | `INSURER_DOCUMENT` or `REGULATORY_DOCUMENT` |

### The 17 rule categories and how many of each exist

| Category | Count | What it checks |
|---|---|---|
| `POLICY_VERSION_RULE` | 16 | General policy terms (free-look period, moratorium, portability, renewal rules) — informational, not auto-evaluated |
| `PREAUTH_REQUIREMENT` | 5 | Pre-authorization lead time / response time rules |
| `CLAIM_FILING_DEADLINE` | 5 | How many days after discharge a claim must be filed |
| `PED_WAITING_PERIOD` | 4 | Waiting period for **P**re-**E**xisting **D**iseases (e.g. 36 months) |
| `SUB_LIMIT` | 4 | Caps on specific treatment categories (e.g. Home Care Treatment capped at 10% of Sum Insured) |
| `INITIAL_WAITING_PERIOD` | 3 | The very first waiting period (e.g. 30 days before ANY illness is covered) |
| `SPECIFIED_DISEASE_WAITING_PERIOD` | 3 | Waiting period for a specific list of diseases (e.g. cataract, hernia — 24 months) |
| `EXCLUSION` | 3 | Things never covered (e.g. cosmetic surgery unless reconstructive) |
| `POLICY_INACTIVE` | 3 | Cancellation notice period rules |
| `ROOM_RENT_LIMIT` | 2 | Cap on daily room rent as % of Sum Insured |
| `DEDUCTIBLE` | 2 | Optional amount the policyholder must pay before insurer pays anything |
| `CLAIM_NOTIFICATION_DEADLINE` | 2 | How fast the insurer must be told about a hospitalization |
| `NON_COVERED_TREATMENT` | 2 | Specific treatments never covered |
| `POLICY_EXPIRED` | 2 | Rules around what happens if a product is withdrawn |
| `CO_PAYMENT` | 1 | Percentage the policyholder pays on every claim (e.g. 10% co-pay if entry age ≥ 61) |
| `GRACE_PERIOD` | 1 | Extra days allowed to pay premium without losing coverage |
| `DOCUMENTATION_MISSING` | 1 | Documents required above a certain claim size (e.g. KYC required above ₹1 lakh) |
| **`ELIGIBILITY_FAILURE`** | **0** | **None extracted yet — honestly absent, not faked** |

### Split by source

- **49 rules** came from the 4 insurer documents (Star Health + HDFC ERGO, both versions)
- **10 rules** came from the IRDAI regulatory circular

### A worked example — reading one real row end to end

Take `SA26-002`:
```
rule_type:        SPECIFIED_DISEASE_WAITING_PERIOD
value / unit:      24 / MONTHS
source_document:   STAR_ASSURE_2026_CIS
source_page:       7
source_text:       "Expenses related to the treatment of the listed
                    Conditions, surgeries/treatments shall be excluded
                    until the expiry of 24 months of continuous
                    coverage after the date of inception of the first
                    policy with us."
review_status:     PENDING
```
Read this as: *"Star Health's actual CIS document, page 7, says word-for-word that certain listed conditions (like cataract) have a 24-month wait. We pulled that number directly from that sentence — we didn't guess 24 months because it's a 'typical' industry number."*

---

## PART 5 — THE UIN CONFLICT (the most important quirk to understand)

A **UIN** (Unique Identification Number) is how IRDAI tracks a specific
version of an insurance product. Normally, all official documents for
one product should show the same UIN.

**They don't, for HDFC ERGO's current 2026 my:Optima Secure product:**

| Document | UIN printed inside it |
|---|---|
| Policy Wording (the full contract) | `HDFHLIP26058V082526` |
| Customer Information Sheet (the summary) | `HDFHLIP25041V062425` |

Both documents are from HDFC ERGO's own official website, fetched the
same day, for what appears to be the same product. **This is a real,
genuine inconsistency in the insurer's own published materials** — not
a mistake we made.

**How the dataset handles this, deliberately:** rather than silently
picking one UIN and pretending there's no problem, every rule extracted
from either of these two 2026 HDFC documents (17 rules total) is marked:
```
review_status = NEEDS_REVIEW
```
This means the rule engine automatically **excludes these rules from
automatic evaluation** until a human resolves the conflict. If you
create a test claim against the HDFC 2026 policy version, you'll see
`overall_result: HUMAN_REVIEW_NEEDED` and a note explaining exactly why.

Full detail, including a side-by-side evidence table, is in
`docs/HDFC_ERGO_UIN_REVIEW.md`.

---

## PART 6 — WHAT'S HONESTLY MISSING (don't hide these from teammates)

- **`ELIGIBILITY_FAILURE` has zero rules.** No age-limit or eligibility
  clause was extracted yet, even though such clauses almost certainly
  exist in the full policy documents.
- **Star Health's full Policy Wording (the detailed contract) was never
  ingested** — only its CIS (summary) was. This means Star Health's
  rule set is less exhaustive than HDFC's.
- **HDFC's 2026 Policy Wording is only ~70% extracted** (pages 1–42 of
  60) — the claims-procedure section and three annexures weren't pulled.
- **`data/processed/pages/` and `data/processed/chunks/`** are empty —
  page-level and chunk-level breakdown (useful for future search/AI
  features) was never built; page markers currently live only inline
  inside the `.txt` files as `[PAGE N]` tags.
- **Only 2 insurers total.** ICICI Lombard, Care Health, and others were
  never attempted (explicitly time-boxed out, not forgotten).
- **The IRDAI circular wasn't fetched directly from irdai.gov.in** — that
  government site blocked automated access, so a verbatim third-party
  republication (matching the exact reference number and date) was used
  instead. Flagged as `official_source = false` in the CSV.

None of this is a "bug" — it's a documented, honest scope boundary. This
is genuinely a *good* thing to show teammates/mentors: it demonstrates
you know exactly what your dataset does and doesn't cover, rather than
overclaiming.

---

## PART 7 — THE 28 SYNTHETIC TEST CLAIMS

`data/synthetic/claims.json` is a list of 28 entries. Every single one
has this shape:

```json
{
  "claim_ref": "SYN-SDW-23mo",
  "policy_version_id": "star_assure_2026_v1",
  "description": "23 months elapsed, cataract",
  "derived_from_rule": "SA26-002",
  "rule_value": "24 MONTHS",
  "case": "BOUNDARY_UNDER",
  "claim_provenance": "SYNTHETIC",
  "expected_result_provenance": "DERIVED_FROM_REAL_RULE",
  "fields": {
    "policy_start_date": "2024-08-23",
    "admission_date": "2026-07-20",
    "diagnosis_description": "Cataract surgery",
    "expected_severity": "FAIL"
  }
}
```

Read this as: *"We made up a fake claim where the policy started
2024-08-23 and admission was 2026-07-20 — that's 23 months apart. We
DELIBERATELY chose 23 months (one short of the real 24-month rule) to
prove the system correctly says FAIL. This isn't a real patient — it's
a boundary test, like a unit test in software engineering."*

### The `case` field tells you WHY each claim exists:
- `BOUNDARY_UNDER` — one unit short of the real threshold (should fail)
- `BOUNDARY_AT` — exactly at the threshold (should pass)
- `BOUNDARY_OVER` — comfortably past the threshold (should pass)
- `POSITIVE` / `NEGATIVE` — for on/off rules like "was the deductible opted into or not"

### Why this matters as a dataset design choice
Every threshold tested (30 days, 24 months, 36 months, 1% room rent,
10% sub-limit, 10% co-pay, 15/30-day filing deadlines, 24hr
notification, 48hr preauth, ₹1 lakh KYC threshold) is a number that
exists in `policy_rule_candidates.csv` — **none of these 28 claims test
a number we made up.** They only exercise numbers already proven to
come from real source text.

---

## PART 8 — HOW TO VERIFY ANY OF THIS YOURSELF, RIGHT NOW

You don't have to trust any of the above — you can check it:

1. **Verify a rule's source is real:** open
   `data/structured/policy_rule_candidates.csv`, pick any row, note its
   `source_document` and `source_page`. Then open the matching file in
   `data/raw/.../*_extracted_text.txt`, search for that `[PAGE N]`
   marker, and read the surrounding text yourself. It'll match the
   `source_text` column exactly.

2. **Verify the dataset has no errors:** run
   ```
   python scripts/validate_dataset.py
   ```
   This regenerates `dataset_validation_report.json` from scratch by
   reading the actual CSVs — it isn't a static file someone hand-edited.

3. **Verify the synthetic claims actually produce the expected result:**
   run
   ```
   python scripts/check_synthetic_claims.py
   ```
   This runs all 28 synthetic claims through the real rule engine and
   reports pass/fail against the `expected_severity` recorded in each
   claim.

---

## ONE-PARAGRAPH SUMMARY (if you only remember one thing)

This dataset contains **5 real policy/regulatory documents**, extracted
into page-numbered text, from which **59 individual rules** were pulled —
each traceable to an exact document, page, and quoted sentence — covering
**17 categories** like waiting periods, sub-limits, co-payments, and
deadlines, for **2 real insurers across 4 policy versions**. Separately,
**28 synthetic (made-up) test claims** exist purely to prove the system
correctly applies those real rule thresholds — they are never real
patients or real insurance decisions. One genuine data-quality issue (a
UIN conflict in HDFC's own official documents) was found and is
deliberately quarantined rather than silently resolved.
