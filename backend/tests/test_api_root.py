"""
Integration tests for the root-level API contract (/health, /policies,
/claims, ...). Uses the SAME 28 synthetic claims already generated in
data/synthetic/claims.json from real rules -- no new claim data invented
here. These synthetic claims are test records only; they are never
represented as real-world insurance claims.
"""
import json
import os

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
)


def _load_synthetic_claims():
    with open(os.path.join(DATA_DIR, "synthetic", "claims.json")) as f:
        return json.load(f)


def test_root_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_root_policies_list_and_detail(client):
    r = client.get("/policies")
    assert r.status_code == 200
    policies = r.json()
    assert len(policies) >= 2
    pid = policies[0]["policy_id"]

    r2 = client.get(f"/policies/{pid}")
    assert r2.status_code == 200
    detail = r2.json()
    assert detail["policy_id"] == pid
    assert "versions" in detail

    r3 = client.get("/policies/999999")
    assert r3.status_code == 404


def test_root_policy_rules_and_sources(client):
    r = client.get("/policies")
    star_policy = [p for p in r.json() if "Star" in p["insurer"]][0]
    pid = star_policy["policy_id"]

    r2 = client.get(f"/policies/{pid}/rules")
    assert r2.status_code == 200
    assert len(r2.json()) >= 1

    r3 = client.get(f"/policies/{pid}/sources")
    assert r3.status_code == 200
    assert len(r3.json()) >= 1


def test_root_claim_lifecycle_and_source_contract(client):
    r = client.post("/claims", json={
        "claim_ref": "ROOT-API-1",
        "policy_version_id": "star_assure_2026_v1",
        "policy_start_date": "2024-08-23",
        "admission_date": "2026-07-20",
        "diagnosis_description": "Cataract surgery",
        "billed_amount": 100000,
    })
    assert r.status_code == 200
    claim_id = r.json()["claim_id"]

    r2 = client.get(f"/claims/{claim_id}")
    assert r2.status_code == 200

    r3 = client.post(f"/claims/{claim_id}/validate")
    assert r3.status_code == 200
    body = r3.json()
    assert body["overall_result"] in (
        "SUBMISSION_READY", "HUMAN_REVIEW_NEEDED", "FIX_BEFORE_SUBMISSION",
    )
    assert len(body["results"]) >= 1
    for result in body["results"]:
        for field in ("rule_id", "category", "severity", "reason", "expected", "actual", "source", "provenance"):
            assert field in result, f"missing field {field} in {result}"
        assert "document" in result["source"]
        assert "page" in result["source"]

    r4 = client.get(f"/claims/{claim_id}/validation")
    assert r4.status_code == 200
    assert r4.json()["overall_result"] == body["overall_result"]


def test_root_all_28_synthetic_claims_via_api(client):
    """Post and validate every one of the 28 real synthetic claims through
    the root-level API, confirming each produces the expected severity for
    its derived_from_rule -- exactly mirroring
    scripts/check_synthetic_claims.py, but via HTTP instead of direct
    engine calls."""
    synthetic_claims = _load_synthetic_claims()
    assert len(synthetic_claims) == 28

    mismatches = []
    for i, sc in enumerate(synthetic_claims):
        payload = {
            "claim_ref": f"{sc['claim_ref']}-API-{i}",
            "policy_version_id": sc["policy_version_id"],
        }
        fields = dict(sc["fields"])
        expected_severity = fields.pop("expected_severity")
        payload.setdefault("policy_start_date", fields.pop("policy_start_date", "2020-01-01"))
        payload.setdefault("admission_date", fields.pop("admission_date", "2026-01-01"))
        payload.update(fields)

        r = client.post("/claims", json=payload)
        assert r.status_code == 200, r.text
        claim_id = r.json()["claim_id"]

        r2 = client.post(f"/claims/{claim_id}/validate")
        assert r2.status_code == 200, r2.text
        results = r2.json()["results"]
        matches = [res for res in results if res["rule_id"] == sc["derived_from_rule"]]

        if expected_severity == "NOT_APPLICABLE":
            ok = len(matches) == 0
        else:
            ok = len(matches) == 1 and matches[0]["severity"] == expected_severity

        if not ok:
            mismatches.append((sc["claim_ref"], sc["derived_from_rule"], expected_severity,
                                matches[0]["severity"] if matches else "MISSING"))

    assert mismatches == [], f"Mismatches: {mismatches}"


def test_policy_version_isolation_star_never_sees_hdfc(client):
    r_star = client.post("/claims", json={
        "claim_ref": "ISO-STAR", "policy_version_id": "star_assure_2026_v1",
        "policy_start_date": "2020-01-01", "admission_date": "2026-01-01",
    })
    star_id = r_star.json()["claim_id"]
    star_results = client.post(f"/claims/{star_id}/validate").json()["results"]

    r_hdfc = client.post("/claims", json={
        "claim_ref": "ISO-HDFC21", "policy_version_id": "hdfc_optima_secure_2021_v1",
        "policy_start_date": "2021-01-01", "admission_date": "2021-06-01",
    })
    hdfc_id = r_hdfc.json()["claim_id"]
    hdfc_results = client.post(f"/claims/{hdfc_id}/validate").json()["results"]

    assert not any(res["rule_id"].startswith("HDFC") for res in star_results)
    assert not any(res["rule_id"].startswith("SA26") for res in hdfc_results)
    assert any(res["rule_id"].startswith("SA26") for res in star_results)
    assert any(res["rule_id"].startswith("HDFC21") for res in hdfc_results)
