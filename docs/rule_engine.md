# Rule Engine

All evaluation logic is deterministic Python. No LLM call occurs anywhere
in `backend/app/rules/` or `backend/app/services/financial_calculator.py`.

## Supported rule categories and their evaluators

| Category | Module | Status | Active rules in dataset |
|---|---|---|---|
| INITIAL_WAITING_PERIOD | `waiting_period.py` | Real | 2 |
| PED_WAITING_PERIOD | `waiting_period.py` | Real | 3 |
| SPECIFIED_DISEASE_WAITING_PERIOD | `waiting_period.py` | Real | 2 |
| EXCLUSION | `exclusion.py` | Real (keyword-overlap, WARNING only) | 2 |
| NON_COVERED_TREATMENT | `exclusion.py` | Real (keyword-overlap, WARNING only) | 1 |
| ROOM_RENT_LIMIT | `room_rent.py` | Real (one band; proportionate-deduction rupee figure not computed, see limitation) | 1 |
| SUB_LIMIT | `sublimit.py` | Real | 3 |
| CO_PAYMENT | `copay.py` | Real | 1 |
| DEDUCTIBLE | `deductible.py` | Real (optional-cover semantics respected) | 1 |
| CLAIM_FILING_DEADLINE | `deadline.py` | Real | 4 |
| CLAIM_NOTIFICATION_DEADLINE | `deadline.py` | Real (day-granularity limitation, see below) | 2 |
| PREAUTH_REQUIREMENT | `preauth.py` | Real (only policyholder-side lead-time rule; insurer-side TAT rules intentionally not evaluated) | 1 of 4 |
| DOCUMENTATION_MISSING | `documentation.py` | Real | 1 |
| ELIGIBILITY_FAILURE | `eligibility.py` | Honest empty stub — 0 rows of this type exist in the dataset | 0 |
| POLICY_INACTIVE | `policy_status.py` | Derived business logic, NOT tied to a specific extracted rule text (see module docstring) | n/a |
| POLICY_EXPIRED | `policy_status.py` | Derived business logic, NOT tied to a specific extracted rule text (see module docstring) | n/a |

## Severity mapping actually used

- **PASS** — condition satisfied.
- **FAIL** — waiting-period violation, or a `policy_status.py` derived
  check failing (admission after cancellation/expiry). Only these push
  `overall_result` to `FIX_BEFORE_SUBMISSION`.
- **PARTIAL_DEDUCTION** — room rent over limit, sub-limit exceeded,
  co-payment applies, deductible applies. Feeds `financial_calculator.py`.
- **WARNING** — late claim filing/notification, short preauth lead time,
  missing KYC documentation, keyword-overlap exclusion match, or an
  unresolved `NEEDS_REVIEW` rule. Never auto-escalated to FAIL.

`overall_result` logic (`engine.py`):
```
any FAIL                          -> FIX_BEFORE_SUBMISSION
any NEEDS_REVIEW rule or WARNING  -> HUMAN_REVIEW_NEEDED
otherwise                         -> SUBMISSION_READY
```
Individual results are always returned in full regardless of the overall
result — nothing is hidden.

## Policy-version isolation

Every evaluator receives only the `PolicyRule` rows already filtered by
`engine.py` to `claim.policy_version_db_id`. Verified directly:
- `test_full_policy_version_isolation` — a Star 2026 claim and an HDFC
  2021 claim, run back to back, share zero rule IDs.
- `test_hdfc_2026_needs_review_rules_not_auto_activated` — HDFC 2026's
  UIN-conflicted rules are surfaced as unresolved (`HUMAN_REVIEW_NEEDED`)
  rather than silently applied.

## Financial calculator

See `backend/app/services/financial_calculator.py` docstring for the
documented reasoning behind the sub-limit → deductible → co-pay order
(Star's own CIS lists sub-limit/co-pay/deductible in that section order;
HDFC's Policy Wording states deductible is applied first in its own
"Utilization of Sum Insured" sequence — the two source documents actually
disagree, so the chosen order is logged in every response rather than
silently assumed). Room-rent proportionate deduction is flagged but not
computed to an exact rupee figure, because no extracted rule states the
proportionality formula precisely (see `room_rent.py`).

All financial output carries the label:
`"RULE-BASED ESTIMATE -- NOT A GUARANTEED INSURER PAYOUT"`

## Known limitations (see also docs/limitations.md)

1. `Claim.admission_date` / `notification_date` etc. are `Date` columns
   (day granularity), not `DateTime`. This means a 24-hour vs 25-hour
   notification deadline cannot be distinguished sub-day — the synthetic
   test suite works around this by using a clearly-over-24h (48h) gap
   instead of fabricating sub-day precision the schema doesn't store.
2. Room-rent proportionate deduction, when triggered, is surfaced as
   `PARTIAL_DEDUCTION` with an explanatory note rather than an exact rupee
   figure, because the specific proportionality clause text was not
   captured with enough precision in this session's extraction pass.
3. `exclusion.py` uses keyword overlap, not clinical/semantic matching. It
   is deliberately capped at WARNING severity for this reason — it can
   surface a possible exclusion for human review, but must never assert a
   FAIL on keyword overlap alone.
4. `eligibility.py`, and the `policy_status.py` derived checks, are
   honestly incomplete/limited as documented in their own module
   docstrings — extending them requires first adding genuinely page-cited
   rule rows to `policy_rule_candidates.csv`.
5. `preauth.py` only evaluates the policyholder-facing 48-hour lead-time
   rule. The three insurer-facing TAT rules (1hr cashless preauth, 3hr
   discharge authorization) describe insurer performance obligations that
   a submitted claim's own fields cannot verify, and are intentionally
   left unevaluated rather than faked.

## Bugs found and fixed during this session's testing

- `sublimit.py`'s original `_extract_cap()` parsed the sub-limit
  percentage from the rule's `unit` string (e.g.
  `PERCENT_OF_SUM_INSURED_MAX_RS_5_LAKHS`), which coincidentally contains
  the digit `5` from `5_LAKHS` — producing a silently-wrong 5% instead of
  the correct 10% from `rule.value`. Caught by
  `test_sublimit_home_care_boundary`, fixed by always reading the
  percentage from `rule.value` and only reading the absolute cap from
  `rule.unit`.
