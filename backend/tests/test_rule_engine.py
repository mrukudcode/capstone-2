"""
Tests use ONLY real values pulled from data/structured/policy_rule_candidates.csv
(SA26-001..020, HDFC21-*, IRDAI-*). No invented policy thresholds.
"""
from datetime import date, timedelta
from app.models.models import Claim, PolicyVersion
from app.rules.engine import validate_claim


def _pv(db, policy_version_id):
    return db.query(PolicyVersion).filter_by(policy_version_id=policy_version_id).first()


def _mk_claim(db, **kwargs):
    pv = _pv(db, kwargs.pop("policy_version_id"))
    claim = Claim(policy_version_db_id=pv.id, **kwargs)
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


# ---------- Waiting periods (already-established, re-confirmed here) ----------

def test_specified_disease_waiting_period_boundary(db):
    # SA26-002: 24 months. 23mo -> FAIL, 24mo exactly -> PASS, 25mo -> PASS
    for months, expect_fail in [(23, True), (24, False), (25, False)]:
        start = date(2024, 1, 1)
        admission = start + timedelta(days=months * 30)
        claim = _mk_claim(db, claim_ref=f"T-SDW-{months}", policy_version_id="star_assure_2026_v1",
                           policy_start_date=start, admission_date=admission)
        run, results, fin = validate_claim(db, claim)
        sdw = [r for r in results if r["rule_id"] == "SA26-002"]
        assert len(sdw) == 1
        assert (sdw[0]["severity"] == "FAIL") == expect_fail


def test_initial_waiting_period_boundary(db):
    # SA26-001: 30 days
    for days, expect_fail in [(29, True), (30, False), (31, False)]:
        start = date(2026, 1, 1)
        admission = start + timedelta(days=days)
        claim = _mk_claim(db, claim_ref=f"T-IWP-{days}", policy_version_id="star_assure_2026_v1",
                           policy_start_date=start, admission_date=admission)
        run, results, fin = validate_claim(db, claim)
        iwp = [r for r in results if r["rule_id"] == "SA26-001"]
        assert (iwp[0]["severity"] == "FAIL") == expect_fail


# ---------- Room rent (SA26-005: 1% of SI/day, 5/7.5L band) ----------

def test_room_rent_limit_boundary(db):
    sum_insured = 500000  # 5 lakhs -> limit = 5000/day
    for rent, expect_partial in [(4999, False), (5000, False), (5001, True)]:
        claim = _mk_claim(
            db, claim_ref=f"T-RR-{rent}", policy_version_id="star_assure_2026_v1",
            policy_start_date=date(2020, 1, 1), admission_date=date(2026, 1, 1),
            sum_insured=sum_insured, room_rent_per_day=rent,
        )
        run, results, fin = validate_claim(db, claim)
        rr = [r for r in results if r["rule_id"] == "SA26-005"]
        assert len(rr) == 1
        assert (rr[0]["severity"] == "PARTIAL_DEDUCTION") == expect_partial


def test_room_rent_out_of_band_not_evaluated(db):
    # 10L+ band explicitly uses "Any Room" per rule's own exception text --
    # rule must NOT fire at all for this band.
    claim = _mk_claim(
        db, claim_ref="T-RR-10L", policy_version_id="star_assure_2026_v1",
        policy_start_date=date(2020, 1, 1), admission_date=date(2026, 1, 1),
        sum_insured=1000000, room_rent_per_day=50000,
    )
    run, results, fin = validate_claim(db, claim)
    assert [r for r in results if r["rule_id"] == "SA26-005"] == []


# ---------- Sub-limit (SA26-006: Home Care, 10% of SI max Rs.5L) ----------

def test_sublimit_home_care_boundary(db):
    sum_insured = 2000000  # 10% = 200000, cap 500000 -> effective limit 200000
    for billed, expect_partial in [(199999, False), (200000, False), (200001, True)]:
        claim = _mk_claim(
            db, claim_ref=f"T-SL-{billed}", policy_version_id="star_assure_2026_v1",
            policy_start_date=date(2020, 1, 1), admission_date=date(2026, 1, 1),
            sum_insured=sum_insured, treatment_category="Home Care Treatment",
            category_billed_amount=billed,
        )
        run, results, fin = validate_claim(db, claim)
        sl = [r for r in results if r["rule_id"] == "SA26-006"]
        assert len(sl) == 1
        assert (sl[0]["severity"] == "PARTIAL_DEDUCTION") == expect_partial


# ---------- Co-payment (SA26-008: age>=61 -> 10%) ----------

def test_copay_age_boundary(db):
    for age, expect_copay in [(60, False), (61, True), (62, True)]:
        claim = _mk_claim(
            db, claim_ref=f"T-COPAY-{age}", policy_version_id="star_assure_2026_v1",
            policy_start_date=date(2020, 1, 1), admission_date=date(2026, 1, 1),
            insured_age_at_entry=age, billed_amount=100000,
        )
        run, results, fin = validate_claim(db, claim)
        cp = [r for r in results if r["rule_id"] == "SA26-008"]
        assert len(cp) == 1
        assert (cp[0]["severity"] == "PARTIAL_DEDUCTION") == expect_copay


# ---------- Deductible (SA26-009: optional, only if opted) ----------

def test_deductible_only_if_opted(db):
    claim_not_opted = _mk_claim(
        db, claim_ref="T-DED-NOT-OPTED", policy_version_id="star_assure_2026_v1",
        policy_start_date=date(2020, 1, 1), admission_date=date(2026, 1, 1),
        deductible_opted=False, billed_amount=300000,
    )
    run, results, fin = validate_claim(db, claim_not_opted)
    assert [r for r in results if r["rule_id"] == "SA26-009"] == []

    claim_opted = _mk_claim(
        db, claim_ref="T-DED-OPTED", policy_version_id="star_assure_2026_v1",
        policy_start_date=date(2020, 1, 1), admission_date=date(2026, 1, 1),
        deductible_opted=True, deductible_amount_opted=50000, billed_amount=300000,
    )
    run2, results2, fin2 = validate_claim(db, claim_opted)
    ded = [r for r in results2 if r["rule_id"] == "SA26-009"]
    assert len(ded) == 1
    assert ded[0]["severity"] == "PARTIAL_DEDUCTION"


# ---------- Claim filing deadline (SA26-010: 15 days; HDFC21-007: 30 days) ----------

def test_claim_filing_deadline_star(db):
    discharge = date(2026, 1, 1)
    for delta_days, expect_warn in [(14, False), (15, False), (16, True)]:
        claim = _mk_claim(
            db, claim_ref=f"T-CFD-{delta_days}", policy_version_id="star_assure_2026_v1",
            policy_start_date=date(2020, 1, 1), admission_date=date(2025, 12, 20),
            discharge_date=discharge, claim_filed_date=discharge + timedelta(days=delta_days),
        )
        run, results, fin = validate_claim(db, claim)
        cfd = [r for r in results if r["rule_id"] == "SA26-010"]
        assert len(cfd) == 1
        assert (cfd[0]["severity"] == "WARNING") == expect_warn


def test_claim_filing_deadline_hdfc_2021_isolated(db):
    # HDFC21-007 (30 days) must not appear on a Star claim, and vice versa.
    discharge = date(2021, 6, 1)
    claim = _mk_claim(
        db, claim_ref="T-CFD-HDFC21", policy_version_id="hdfc_optima_secure_2021_v1",
        policy_start_date=date(2021, 1, 1), admission_date=date(2021, 5, 20),
        discharge_date=discharge, claim_filed_date=discharge + timedelta(days=31),
    )
    run, results, fin = validate_claim(db, claim)
    ids = {r["rule_id"] for r in results}
    assert "HDFC21-007" in ids
    assert "SA26-010" not in ids
    cfd = [r for r in results if r["rule_id"] == "HDFC21-007"][0]
    assert cfd["severity"] == "WARNING"  # 31 days > 30-day deadline


# ---------- Notification deadline (SA26-012: 24 hours, emergency only) ----------

def test_notification_deadline_emergency_only(db):
    admission = date(2026, 1, 1)
    claim_planned = _mk_claim(
        db, claim_ref="T-NOTIF-PLANNED", policy_version_id="star_assure_2026_v1",
        policy_start_date=date(2020, 1, 1), admission_date=admission,
        claim_type="PLANNED", notification_date=admission + timedelta(days=5),
    )
    run, results, fin = validate_claim(db, claim_planned)
    assert [r for r in results if r["rule_id"] == "SA26-012"] == []

    claim_emergency_late = _mk_claim(
        db, claim_ref="T-NOTIF-EMERG-LATE", policy_version_id="star_assure_2026_v1",
        policy_start_date=date(2020, 1, 1), admission_date=admission,
        claim_type="EMERGENCY", notification_date=admission + timedelta(days=2),
    )
    run2, results2, fin2 = validate_claim(db, claim_emergency_late)
    notif = [r for r in results2 if r["rule_id"] == "SA26-012"]
    assert len(notif) == 1
    assert notif[0]["severity"] == "WARNING"


# ---------- Preauth (SA26-013: 48 hours before planned admission) ----------

def test_preauth_lead_time_boundary(db):
    admission = date(2026, 3, 10)
    for lead_hours, expect_pass in [(47 * 24 // 24, False)]:
        pass  # placeholder to keep structure simple; real cases below

    claim_ok = _mk_claim(
        db, claim_ref="T-PREAUTH-OK", policy_version_id="star_assure_2026_v1",
        policy_start_date=date(2020, 1, 1), admission_date=admission,
        claim_type="PLANNED", preauth_request_date=admission - timedelta(days=3),
    )
    run, results, fin = validate_claim(db, claim_ok)
    pa = [r for r in results if r["rule_id"] == "SA26-013"]
    assert len(pa) == 1 and pa[0]["severity"] == "PASS"

    claim_short = _mk_claim(
        db, claim_ref="T-PREAUTH-SHORT", policy_version_id="star_assure_2026_v1",
        policy_start_date=date(2020, 1, 1), admission_date=admission,
        claim_type="PLANNED", preauth_request_date=admission - timedelta(days=1),
    )
    run2, results2, fin2 = validate_claim(db, claim_short)
    pa2 = [r for r in results2 if r["rule_id"] == "SA26-013"]
    assert len(pa2) == 1 and pa2[0]["severity"] == "WARNING"


# ---------- Documentation (HDFC21-011: KYC required above Rs.1L) ----------

def test_documentation_kyc_threshold(db):
    claim_below = _mk_claim(
        db, claim_ref="T-DOC-BELOW", policy_version_id="hdfc_optima_secure_2021_v1",
        policy_start_date=date(2021, 1, 1), admission_date=date(2021, 6, 1),
        billed_amount=99999, documents_submitted="claim_form,photo_id",
    )
    run, results, fin = validate_claim(db, claim_below)
    assert [r for r in results if r["rule_id"] == "HDFC21-011"] == []

    claim_above_missing_kyc = _mk_claim(
        db, claim_ref="T-DOC-ABOVE-MISSING", policy_version_id="hdfc_optima_secure_2021_v1",
        policy_start_date=date(2021, 1, 1), admission_date=date(2021, 6, 1),
        billed_amount=150000, documents_submitted="claim_form,photo_id",
    )
    run2, results2, fin2 = validate_claim(db, claim_above_missing_kyc)
    doc = [r for r in results2 if r["rule_id"] == "HDFC21-011"]
    assert len(doc) == 1 and doc[0]["severity"] == "WARNING"

    claim_above_with_kyc = _mk_claim(
        db, claim_ref="T-DOC-ABOVE-OK", policy_version_id="hdfc_optima_secure_2021_v1",
        policy_start_date=date(2021, 1, 1), admission_date=date(2021, 6, 1),
        billed_amount=150000, documents_submitted="claim_form,photo_id,KYC",
    )
    run3, results3, fin3 = validate_claim(db, claim_above_with_kyc)
    doc3 = [r for r in results3 if r["rule_id"] == "HDFC21-011"]
    assert len(doc3) == 1 and doc3[0]["severity"] == "PASS"


# ---------- Exclusion (keyword-overlap WARNING, never auto-FAIL) ----------

def test_exclusion_keyword_overlap_is_warning_not_fail(db):
    claim = _mk_claim(
        db, claim_ref="T-EXCL-REFRACTIVE", policy_version_id="star_assure_2026_v1",
        policy_start_date=date(2020, 1, 1), admission_date=date(2026, 1, 1),
        diagnosis_description="Refractive error correction surgery",
    )
    run, results, fin = validate_claim(db, claim)
    excl = [r for r in results if r["rule_id"] == "SA26-015"]
    assert len(excl) == 1
    assert excl[0]["severity"] == "WARNING"  # never FAIL from keyword match alone


# ---------- Policy-version isolation (comprehensive cross-check) ----------

def test_full_policy_version_isolation(db):
    star_claim = _mk_claim(
        db, claim_ref="T-ISO-STAR", policy_version_id="star_assure_2026_v1",
        policy_start_date=date(2020, 1, 1), admission_date=date(2026, 1, 1),
    )
    hdfc_claim = _mk_claim(
        db, claim_ref="T-ISO-HDFC21", policy_version_id="hdfc_optima_secure_2021_v1",
        policy_start_date=date(2021, 1, 1), admission_date=date(2021, 6, 1),
    )
    _, star_results, _ = validate_claim(db, star_claim)
    _, hdfc_results, _ = validate_claim(db, hdfc_claim)

    star_ids = {r["rule_id"] for r in star_results if r["rule_id"].startswith("SA26")}
    hdfc_ids = {r["rule_id"] for r in hdfc_results if r["rule_id"].startswith("HDFC21")}
    assert star_ids, "Star claim should evaluate at least one SA26 rule"
    assert hdfc_ids, "HDFC 2021 claim should evaluate at least one HDFC21 rule"

    # No cross-contamination in either direction.
    assert not any(r["rule_id"].startswith("HDFC") for r in star_results)
    assert not any(r["rule_id"].startswith("SA26") for r in hdfc_results)


def test_hdfc_2026_needs_review_rules_not_auto_activated(db):
    # HDFC 2026 rules are all NEEDS_REVIEW pending UIN conflict resolution.
    claim = _mk_claim(
        db, claim_ref="T-HDFC26-NEEDSREVIEW", policy_version_id="hdfc_optima_secure_2026_v1",
        policy_start_date=date(2020, 1, 1), admission_date=date(2026, 6, 1),
    )
    run, results, fin = validate_claim(db, claim)
    assert run.overall_result == "HUMAN_REVIEW_NEEDED"
    assert any(r["actual"] == "NOT_EVALUATED" for r in results)


# ---------- API integration ----------

def test_api_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200


def test_api_full_flow(client):
    r = client.post("/api/claims", json={
        "claim_ref": "API-FLOW-1",
        "policy_version_id": "star_assure_2026_v1",
        "policy_start_date": "2024-01-01",
        "admission_date": "2026-06-01",
        "diagnosis_description": "Hernia surgery",
        "billed_amount": 200000,
    })
    assert r.status_code == 200
    claim_id = r.json()["claim_id"]

    r2 = client.post(f"/api/claims/{claim_id}/validate")
    assert r2.status_code == 200
    body = r2.json()
    assert "overall_result" in body
    assert "financials" in body
    assert body["financials"]["label"].startswith("RULE-BASED ESTIMATE")

    r3 = client.get(f"/api/claims/{claim_id}/validation")
    assert r3.status_code == 200
    assert r3.json()["overall_result"] == body["overall_result"]


def test_api_policies_endpoints(client):
    r = client.get("/api/policies")
    assert r.status_code == 200
    policies = r.json()
    assert len(policies) >= 2
    star_policy = [p for p in policies if "Star" in p["insurer"]][0]

    r2 = client.get(f"/api/policies/{star_policy['policy_id']}/versions")
    assert r2.status_code == 200
    assert len(r2.json()) >= 1

    r3 = client.get(f"/api/policies/{star_policy['policy_id']}/rules")
    assert r3.status_code == 200

    r4 = client.get(f"/api/policies/{star_policy['policy_id']}/sources")
    assert r4.status_code == 200
