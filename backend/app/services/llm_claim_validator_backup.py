import json
from app.services.llm_service import call_llm


SYSTEM_PROMPT = """
You are an expert Indian health insurance policy analysis assistant.

Your task is to compare ONE CLAIM against ONE EXTRACTED POLICY RULE.

Use ONLY:
1. The claim data provided.
2. The extracted policy rule.
3. The source text provided.

Do NOT use general insurance knowledge.
Do NOT invent missing facts.
Do NOT assume a rule applies when its condition is not satisfied.

First determine whether the rule applies.

Then determine whether the claim satisfies the rule.

Return ONLY valid JSON.

Required JSON format:

{
  "applicable": true,
  "compliant": true,
  "finding": "PASS",
  "reason": "Short explanation",
  "expected": "What the policy requires",
  "actual": "What the claim contains",
  "confidence": 0.95
}

Possible values for "finding":

PASS
LIMIT_EXCEEDED
REQUIREMENT_MISSING
EXCLUSION_MATCH
WAITING_PERIOD_NOT_MET
DEADLINE_EXCEEDED
PREAUTH_REQUIREMENT_NOT_MET
ELIGIBILITY_VIOLATION
AMBIGUOUS
INSUFFICIENT_DATA

Important:

- PASS means the claim satisfies the applicable rule.
- LIMIT_EXCEEDED means a numeric or monetary policy limit has been exceeded.
- REQUIREMENT_MISSING means a required document/data/action is missing.
- EXCLUSION_MATCH means the claim appears to match an explicit exclusion.
- WAITING_PERIOD_NOT_MET means an explicit waiting period has not been satisfied.
- DEADLINE_EXCEEDED means an explicit claim deadline was exceeded.
- PREAUTH_REQUIREMENT_NOT_MET means an explicit preauthorization requirement was not satisfied.
- ELIGIBILITY_VIOLATION means an explicit eligibility condition was violated.
- AMBIGUOUS means the rule or claim cannot be confidently interpreted.
- INSUFFICIENT_DATA means required claim information is missing.

Never decide the final financial consequence such as FAIL or PARTIAL_DEDUCTION.
The application will determine that separately.

confidence must be between 0 and 1.
"""


def validate_claim_against_rule(claim_data, rule, source_text=""):
    prompt = f"""
Compare the following claim against the following policy rule.

CLAIM DATA:
{json.dumps(claim_data, indent=2, default=str)}

POLICY RULE:
{json.dumps(rule, indent=2, default=str)}

SOURCE TEXT:
{source_text}

Return ONLY the required JSON object.
"""

    response = call_llm(
        SYSTEM_PROMPT,
        prompt
    )

    cleaned = response.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "", 1)
        cleaned = cleaned.replace("```", "", 1)
        cleaned = cleaned.replace("```", "", 1)
        cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"LLM returned invalid JSON:\n{response}"
        ) from e

    required_fields = [
        "applicable",
        "compliant",
        "finding",
        "reason",
        "expected",
        "actual",
        "confidence",
    ]

    missing = [field for field in required_fields if field not in result]

    if missing:
        raise ValueError(
            f"LLM response missing fields: {missing}\nResponse: {result}"
        )

    return result