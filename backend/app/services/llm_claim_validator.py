"""
LLM-assisted claim validation using Groq.

Responsibilities
----------------

This module performs semantic policy interpretation only.

It does NOT:
    - calculate financial deductions
    - calculate deadlines
    - calculate waiting-period durations
    - predict insurer approval
    - predict insurer rejection
    - guarantee claim payout

The caller supplies:
    1. one policy rule
    2. one claim
    3. optional source text

The model returns one structured JSON validation result.
"""

import os
import json
from typing import Any, Dict, Optional

from groq import Groq


# ================================================================
# CONFIGURATION
# ================================================================

DEFAULT_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

MAX_SOURCE_TEXT_CHARS = 6000

GROQ_TIMEOUT = float(
    os.getenv(
        "GROQ_TIMEOUT",
        "30"
    )
)

GROQ_MAX_RETRIES = int(
    os.getenv(
        "GROQ_MAX_RETRIES",
        "0"
    )
)


# ================================================================
# GROQ CLIENT
# ================================================================

def _get_client() -> Groq:

    api_key = os.getenv(
        "GROQ_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "GROQ_API_KEY environment variable is not set."
        )

    return Groq(
        api_key=api_key,
        timeout=GROQ_TIMEOUT,
        max_retries=GROQ_MAX_RETRIES
    )


# ================================================================
# SAFE VALUE
# ================================================================

def _safe_value(value: Any) -> Any:
    """
    Convert Python / SQLAlchemy values into JSON-safe values.
    """

    if value is None:
        return None

    if isinstance(
        value,
        (str, int, float, bool)
    ):
        return value

    # Decimal
    try:

        from decimal import Decimal

        if isinstance(
            value,
            Decimal
        ):
            return float(value)

    except Exception:
        pass

    # date / datetime
    try:

        from datetime import date, datetime

        if isinstance(
            value,
            (date, datetime)
        ):
            return value.isoformat()

    except Exception:
        pass

    # Enum
    try:

        if hasattr(
            value,
            "value"
        ):
            return value.value

    except Exception:
        pass

    return str(value)


# ================================================================
# CLAIM -> DICTIONARY
# ================================================================

def _claim_to_dict(
    claim_data: Any
) -> Dict[str, Any]:
    """
    Convert:
        - SQLAlchemy Claim
        - dictionary
        - generic object

    into JSON-safe dictionary.
    """

    if claim_data is None:
        return {}

    # Dictionary
    if isinstance(
        claim_data,
        dict
    ):

        return {
            str(key): _safe_value(value)
            for key, value in claim_data.items()
        }

    # SQLAlchemy model
    if hasattr(
        claim_data,
        "__table__"
    ):

        result = {}

        for column in claim_data.__table__.columns:

            try:

                result[column.name] = _safe_value(
                    getattr(
                        claim_data,
                        column.name
                    )
                )

            except Exception:
                continue

        return result

    # Generic object
    if hasattr(
        claim_data,
        "__dict__"
    ):

        result = {}

        for key, value in vars(
            claim_data
        ).items():

            if key.startswith("_"):
                continue

            result[key] = _safe_value(
                value
            )

        return result

    return {
        "claim": _safe_value(
            claim_data
        )
    }


# ================================================================
# RULE -> DICTIONARY
# ================================================================

def _rule_to_dict(
    rule: Any
) -> Dict[str, Any]:
    """
    Convert:
        - SQLAlchemy PolicyRule
        - dictionary
        - generic object

    into JSON-safe dictionary.
    """

    if rule is None:
        return {}

    # Dictionary
    if isinstance(
        rule,
        dict
    ):

        return {
            str(key): _safe_value(value)
            for key, value in rule.items()
        }

    # SQLAlchemy model
    if hasattr(
        rule,
        "__table__"
    ):

        result = {}

        for column in rule.__table__.columns:

            try:

                result[column.name] = _safe_value(
                    getattr(
                        rule,
                        column.name
                    )
                )

            except Exception:
                continue

        return result

    # Generic object
    if hasattr(
        rule,
        "__dict__"
    ):

        result = {}

        for key, value in vars(
            rule
        ).items():

            if key.startswith("_"):
                continue

            result[key] = _safe_value(
                value
            )

        return result

    return {
        "rule": _safe_value(
            rule
        )
    }


# ================================================================
# STRUCTURED OUTPUT SCHEMA
# ================================================================

VALIDATION_JSON_SCHEMA = {

    "type": "object",

    "properties": {

        "applicable": {
            "type": "boolean"
        },

        "compliant": {
            "type": "boolean"
        },

        "finding": {
            "type": "string",

            "enum": [
                "PASS",
                "FAIL",
                "INSUFFICIENT_DATA",
                "NOT_APPLICABLE"
            ]
        },

        "reason": {
            "type": "string"
        },

        "expected": {
            "type": "string"
        },

        "actual": {
            "type": "string"
        },

        "confidence": {
            "type": "number",

            "minimum": 0,

            "maximum": 1
        }
    },

    "required": [
        "applicable",
        "compliant",
        "finding",
        "reason",
        "expected",
        "actual",
        "confidence"
    ],

    "additionalProperties": False
}


# ================================================================
# SYSTEM PROMPT
# ================================================================

SYSTEM_PROMPT = """
You are a strict health-insurance policy validation engine.

You validate ONE CLAIM against ONE POLICY RULE.

Your task is semantic policy interpretation.

===============================================================
CORE RULES
===============================================================

1. Use ONLY:
   - supplied policy rule
   - supplied claim data
   - supplied policy source text

2. NEVER use outside knowledge.

3. NEVER invent missing claim information.

4. NEVER invent policy conditions.

5. NEVER assume a diagnosis is a pre-existing disease merely because
   it is a chronic disease or because it appears in the claim.

6. NEVER assume that a condition is part of a policy's "listed
   conditions" unless the supplied policy material explicitly
   establishes that.

7. If a required fact is missing, return:

   finding = "INSUFFICIENT_DATA"

8. Missing information must NEVER be treated as PASS.

9. Missing information must NEVER be treated as FAIL.

10. If the rule clearly does not apply to this claim, return:

    applicable = false
    compliant = false
    finding = "NOT_APPLICABLE"

11. If the rule applies and the claim satisfies it:

    applicable = true
    compliant = true
    finding = "PASS"

12. If the rule applies and the claim violates it:

    applicable = true
    compliant = false
    finding = "FAIL"

===============================================================
WAITING PERIOD SAFETY
===============================================================

13. A waiting-period rule does NOT itself prove that a diagnosis is
    a pre-existing disease.

14. If the rule requires determining whether a diagnosis is a
    pre-existing disease and the supplied information does not
    establish this, return INSUFFICIENT_DATA.

15. If the rule refers to a list of diseases/conditions and that list
    is not supplied, do not infer membership from medical knowledge.

16. If a waiting-period duration can be calculated from structured
    dates, the application should prefer deterministic calculation.
    Do not invent dates.

===============================================================
EXCLUSION SAFETY
===============================================================

17. If an exclusion depends on a measurement, threshold, test result,
    procedure, or other factual value and that value is missing,
    return INSUFFICIENT_DATA.

18. Do not assume a missing measurement is within or outside the
    threshold.

===============================================================
POLICY VERSION SAFETY
===============================================================

19. If a policy-version rule depends on a receipt date, inception
    date, cancellation date, renewal date, or other date and that
    date is missing, return INSUFFICIENT_DATA.

===============================================================
OUTPUT
===============================================================

20. Keep reason concise.

21. Keep expected concise.

22. Keep actual concise.

23. Confidence must be between 0 and 1.

24. Return only the structured JSON response.
"""


# ================================================================
# VALIDATION
# ================================================================

def validate_claim_against_rule(
    rule: Any,
    claim_data: Any,
    source_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate one claim against one semantic policy rule.
    """

    # ------------------------------------------------------------
    # Convert objects
    # ------------------------------------------------------------

    rule_dict = _rule_to_dict(
        rule
    )

    claim_dict = _claim_to_dict(
        claim_data
    )

    # ------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------

    rule_json = json.dumps(
        rule_dict,
        indent=2,
        ensure_ascii=False,
        default=str
    )

    claim_json = json.dumps(
        claim_dict,
        indent=2,
        ensure_ascii=False,
        default=str
    )

    # ------------------------------------------------------------
    # Source text
    # ------------------------------------------------------------

    source_section = ""

    if source_text:

        source_text_clean = str(
            source_text
        ).strip()

        if len(
            source_text_clean
        ) > MAX_SOURCE_TEXT_CHARS:

            source_text_clean = (
                source_text_clean[
                    :MAX_SOURCE_TEXT_CHARS
                ]
                + "\n[POLICY SOURCE TRUNCATED]"
            )

        source_section = f"""
POLICY SOURCE TEXT
------------------
{source_text_clean}
"""

    # ------------------------------------------------------------
    # User prompt
    # ------------------------------------------------------------

    user_prompt = f"""
POLICY RULE
-----------
{rule_json}

CLAIM DATA
----------
{claim_json}

{source_section}

Validate this claim against ONLY this policy rule.

Important:

- Do not use outside medical knowledge.
- Do not assume a diagnosis is a PED.
- Do not assume a diagnosis belongs to a policy's listed-condition
  list unless supplied evidence establishes this.
- Do not treat missing information as PASS.
- Do not treat missing information as FAIL.
- If a required fact is missing, return INSUFFICIENT_DATA.
- If the rule clearly does not apply, return NOT_APPLICABLE.

Return the structured validation result.
"""

    # ------------------------------------------------------------
    # Client
    # ------------------------------------------------------------

    client = _get_client()

    # ------------------------------------------------------------
    # Groq call
    # ------------------------------------------------------------

    response = client.chat.completions.create(

        model=DEFAULT_MODEL,

        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],

        temperature=0,

        response_format={
            "type": "json_schema",

            "json_schema": {

                "name":
                    "claim_rule_validation",

                "strict":
                    True,

                "schema":
                    VALIDATION_JSON_SCHEMA
            }
        },

        reasoning_effort="low",

        max_completion_tokens=400
    )

    # ------------------------------------------------------------
    # Response validation
    # ------------------------------------------------------------

    if not response.choices:

        raise ValueError(
            "LLM returned no choices."
        )

    content = (
        response
        .choices[0]
        .message
        .content
    )

    if not content:

        raise ValueError(
            "LLM returned empty response."
        )

    content = content.strip()

    # ------------------------------------------------------------
    # Parse JSON
    # ------------------------------------------------------------

    try:

        parsed = json.loads(
            content
        )

    except json.JSONDecodeError as exc:

        raise ValueError(
            f"LLM returned invalid JSON: {content}"
        ) from exc

    # ------------------------------------------------------------
    # Required fields
    # ------------------------------------------------------------

    required_fields = [
        "applicable",
        "compliant",
        "finding",
        "reason",
        "expected",
        "actual",
        "confidence"
    ]

    for field in required_fields:

        if field not in parsed:

            raise ValueError(
                f"LLM response missing required field: {field}"
            )

    # ------------------------------------------------------------
    # Read
    # ------------------------------------------------------------

    applicable = parsed[
        "applicable"
    ]

    compliant = parsed[
        "compliant"
    ]

    finding = parsed[
        "finding"
    ]

    reason = parsed[
        "reason"
    ]

    expected = parsed[
        "expected"
    ]

    actual = parsed[
        "actual"
    ]

    confidence = parsed[
        "confidence"
    ]

    # ------------------------------------------------------------
    # Validate finding
    # ------------------------------------------------------------

    valid_findings = {
        "PASS",
        "FAIL",
        "INSUFFICIENT_DATA",
        "NOT_APPLICABLE"
    }

    if finding not in valid_findings:

        raise ValueError(
            f"Invalid finding returned by LLM: {finding}"
        )

    # ------------------------------------------------------------
    # Validate booleans
    # ------------------------------------------------------------

    if not isinstance(
        applicable,
        bool
    ):

        raise ValueError(
            "LLM returned invalid applicable value."
        )

    if not isinstance(
        compliant,
        bool
    ):

        raise ValueError(
            "LLM returned invalid compliant value."
        )

    # ------------------------------------------------------------
    # Validate confidence
    # ------------------------------------------------------------

    try:

        confidence = float(
            confidence
        )

    except (
        TypeError,
        ValueError
    ):

        confidence = 0.0

    confidence = max(
        0.0,
        min(
            1.0,
            confidence
        )
    )

    # ------------------------------------------------------------
    # Safety normalization
    #
    # Prevent logically inconsistent combinations.
    # ------------------------------------------------------------

    if finding == "PASS":

        applicable = True
        compliant = True

    elif finding == "FAIL":

        applicable = True
        compliant = False

    elif finding == "INSUFFICIENT_DATA":

        compliant = False

    elif finding == "NOT_APPLICABLE":

        applicable = False
        compliant = False

    # ------------------------------------------------------------
    # Return
    # ------------------------------------------------------------

    return {

        "applicable":
            applicable,

        "compliant":
            compliant,

        "finding":
            finding,

        "reason":
            str(reason),

        "expected":
            str(expected),

        "actual":
            str(actual),

        "confidence":
            confidence
    }


# ================================================================
# BACKWARD COMPATIBILITY
# ================================================================

def validate_claim(
    rule: Any,
    claim_data: Any,
    source_text: Optional[str] = None
) -> Dict[str, Any]:

    return validate_claim_against_rule(
        rule=rule,
        claim_data=claim_data,
        source_text=source_text
    )