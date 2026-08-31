import json
from app.services.llm_service import call_llm


SYSTEM_PROMPT = """
You are an expert Indian health insurance policy analyst.

Your task is to extract explicit, verifiable insurance rules from policy text.

Do NOT invent rules.
Do NOT use general insurance knowledge.
Only extract rules that are explicitly supported by the provided text.

Return ONLY valid JSON.

The JSON must be an array of objects with these fields:

[
  {
    "rule_type": "string",
    "rule_name": "string",
    "condition": "string",
    "value": "string",
    "unit": "string",
    "applies_to": "string",
    "exception": "string",
    "source_section": "string",
    "reasoning": "string"
  }
]

Possible rule_type values include:

INITIAL_WAITING_PERIOD
PED_WAITING_PERIOD
SPECIFIED_DISEASE_WAITING_PERIOD
ROOM_RENT_LIMIT
SUB_LIMIT
CO_PAYMENT
DEDUCTIBLE
CLAIM_FILING_DEADLINE
CLAIM_NOTIFICATION_DEADLINE
PREAUTH_REQUIREMENT
EXCLUSION
NON_COVERED_TREATMENT
DOCUMENTATION_MISSING
ELIGIBILITY_FAILURE
POLICY_INACTIVE
POLICY_EXPIRED

If a field is not explicitly available, use an empty string.

The reasoning must explain briefly why the text supports the extracted rule.
"""


def extract_rules(policy_text: str):
    response = call_llm(
        SYSTEM_PROMPT,
        f"""
Extract all explicit insurance rules from the following policy text.

POLICY TEXT:
{policy_text}
"""
    )

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        # Handle cases where the model accidentally returns markdown fences.
        cleaned = response.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.replace("```json", "", 1)
            cleaned = cleaned.replace("```", "", 1)
            cleaned = cleaned.strip()

        return json.loads(cleaned)