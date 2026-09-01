"""
LLM-assisted policy rule extraction from uploaded PDF text.

Given raw extracted policy text (page-tagged), asks Groq to identify
concrete, checkable insurance policy rules.

Extracted rules are intended to be stored with:
    review_status = "PENDING"

They must be manually reviewed before being trusted by the
validation engine.
"""

import os
import json
import time
from typing import Any, Dict, List

from groq import Groq


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b",
)

GROQ_TIMEOUT = float(
    os.getenv("GROQ_TIMEOUT", "60")
)

# Number of retries for temporary failures.
# Default = 3.
GROQ_MAX_RETRIES = int(
    os.getenv("GROQ_MAX_RETRIES", "3")
)

# Delay before retrying.
GROQ_RETRY_BASE_DELAY = float(
    os.getenv("GROQ_RETRY_BASE_DELAY", "3")
)

# Keep completion relatively small.
# We do NOT need huge output for one PDF page.
GROQ_MAX_COMPLETION_TOKENS = int(
    os.getenv("GROQ_MAX_COMPLETION_TOKENS", "1800")
)


# ============================================================
# RULE TYPES
# ============================================================

RULE_TYPES = [
    "INITIAL_WAITING_PERIOD",
    "SPECIFIED_DISEASE_WAITING_PERIOD",
    "PED_WAITING_PERIOD",
    "ROOM_RENT_LIMIT",
    "SUB_LIMIT",
    "CO_PAYMENT",
    "DEDUCTIBLE",
    "CLAIM_FILING_DEADLINE",
    "CLAIM_NOTIFICATION_DEADLINE",
    "PREAUTH_REQUIREMENT",
    "POLICY_VERSION_RULE",
    "EXCLUSION",
    "NON_COVERED_TREATMENT",
    "POLICY_INACTIVE",
    "POLICY_EXPIRED",
    "GRACE_PERIOD",
    "DOCUMENTATION_MISSING",
]


# ============================================================
# JSON SCHEMA
# ============================================================

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule_type": {
                        "type": "string",
                        "enum": RULE_TYPES,
                    },

                    "rule_name": {
                        "type": "string",
                    },

                    "condition": {
                        "type": "string",
                    },

                    "value": {
                        "type": "string",
                    },

                    "unit": {
                        "type": "string",
                    },

                    "applies_to": {
                        "type": "string",
                    },

                    "exception": {
                        "type": "string",
                    },

                    "source_page": {
                        "type": "string",
                    },

                    "source_section": {
                        "type": "string",
                    },

                    "source_text": {
                        "type": "string",
                    },

                    "confidence": {
                        "type": "string",
                        "enum": [
                            "HIGH",
                            "MEDIUM",
                            "LOW",
                        ],
                    },
                },

                "required": [
                    "rule_type",
                    "rule_name",
                    "condition",
                    "value",
                    "unit",
                    "applies_to",
                    "exception",
                    "source_page",
                    "source_section",
                    "source_text",
                    "confidence",
                ],

                "additionalProperties": False,
            },
        }
    },

    "required": ["rules"],

    "additionalProperties": False,
}


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a strict health-insurance policy rule extraction engine.

Your job is to extract ONLY concrete, checkable contractual rules
from the supplied Indian health-insurance policy text.

Possible rule categories include:

- Initial waiting periods
- Specific disease waiting periods
- Pre-existing disease waiting periods
- Room rent limits
- ICU limits
- Sub-limits
- Co-payment
- Deductibles
- Claim filing deadlines
- Claim notification deadlines
- Preauthorization requirements
- Exclusions
- Non-covered treatments
- Policy activation rules
- Policy expiry rules
- Grace periods
- Free-look periods
- Portability rules
- Documentation requirements
- Other explicit contractual conditions

STRICT RULES:

1. ONLY extract information explicitly present in the supplied text.

2. NEVER invent:
   - numbers
   - percentages
   - durations
   - conditions
   - exclusions
   - requirements
   - policy benefits

3. Do not infer a rule from general insurance knowledge.

4. source_text MUST be an exact short excerpt from the supplied text.

5. source_text MUST be under 30 words.

6. Use the nearest [PAGE N] marker to determine source_page.

7. If a section or clause identifier is explicitly visible,
   put it in source_section.

8. If no section identifier exists, use an empty string.

9. confidence:
   HIGH = explicit and unambiguous contractual rule.
   MEDIUM = some interpretation was necessary.
   LOW = unclear or ambiguous.

10. Do not extract:
    - marketing statements
    - advertisements
    - generic descriptions
    - premium tables
    - benefit illustrations
    - headings without an actual rule

11. Extract a rule only when it is actually checkable.

12. Preserve the meaning of the original policy.

13. Do not convert vague language into a precise rule.

14. A page may contain ZERO rules.

15. If no concrete rule exists, return:

{
  "rules": []
}

IMPORTANT:

Do not create a DOCUMENTATION_MISSING rule merely because the
text does not contain a rule.

DOCUMENTATION_MISSING should only be used when the policy itself
explicitly states a documentation requirement.

Return ONLY the structured JSON response.
"""


# ============================================================
# GROQ CLIENT
# ============================================================

def _get_client() -> Groq:
    """
    Create the Groq client using the existing GROQ_API_KEY.
    """

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY environment variable is not set."
        )

    return Groq(
        api_key=api_key,
        timeout=GROQ_TIMEOUT,
        max_retries=0,
    )


# ============================================================
# ERROR HELPERS
# ============================================================

def _is_retryable_error(error: Exception) -> bool:
    """
    Determine whether an exception is likely temporary.

    Retry:
        429 = rate limit
        408 = timeout
        409 = temporary conflict
        500+ = server-side failure

    413 can also happen because the request is too large.
    We retry it once, although reducing chunk size is the real fix.
    """

    message = str(error).lower()

    retryable_markers = [
        "429",
        "rate limit",
        "rate_limit",
        "too many requests",
        "408",
        "timeout",
        "timed out",
        "409",
        "413",
        "request too large",
        "500",
        "502",
        "503",
        "504",
        "internal server error",
        "service unavailable",
    ]

    return any(
        marker in message
        for marker in retryable_markers
    )


def _retry_delay(attempt: int) -> float:
    """
    Exponential backoff.

    attempt 0 -> base delay
    attempt 1 -> 2 * base delay
    attempt 2 -> 4 * base delay
    """

    return GROQ_RETRY_BASE_DELAY * (2 ** attempt)


# ============================================================
# EXTRACT ONE CHUNK
# ============================================================

def extract_rules_from_chunk(
    chunk_text: str,
) -> List[Dict[str, Any]]:
    """
    Send one PDF text chunk to Groq and return extracted rules.

    The chunk should already contain [PAGE N] markers.
    """

    if not chunk_text:
        return []

    client = _get_client()

    user_prompt = f"""
POLICY TEXT CHUNK
=================

{chunk_text}

TASK
====

Extract every concrete, checkable insurance-policy rule
explicitly stated in this text.

Remember:

- Do not invent anything.
- Do not infer missing information.
- Do not create documentation-missing errors.
- If there are no rules, return an empty rules array.
- source_text must be an exact excerpt under 30 words.

Return the structured JSON response.
"""

    last_error = None

    for attempt in range(
        GROQ_MAX_RETRIES + 1
    ):

        try:

            response = client.chat.completions.create(
                model=DEFAULT_MODEL,

                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],

                temperature=0,

                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "policy_rule_extraction",
                        "strict": True,
                        "schema": EXTRACTION_SCHEMA,
                    },
                },

                reasoning_effort="low",

                max_completion_tokens=GROQ_MAX_COMPLETION_TOKENS,
            )

            # ------------------------------------------------
            # Validate response
            # ------------------------------------------------

            if not response.choices:
                return []

            message = response.choices[0].message

            if message is None:
                return []

            content = message.content

            if not content:
                return []

            # ------------------------------------------------
            # Parse JSON
            # ------------------------------------------------

            try:

                parsed = json.loads(
                    content.strip()
                )

            except json.JSONDecodeError:

                # Do not create fake rules.
                return []

            if not isinstance(
                parsed,
                dict
            ):
                return []

            rules = parsed.get(
                "rules",
                []
            )

            if not isinstance(
                rules,
                list
            ):
                return []

            return rules

        except Exception as e:

            last_error = e

            # ----------------------------------------------
            # Non-retryable error
            # ----------------------------------------------

            if not _is_retryable_error(e):

                raise

            # ----------------------------------------------
            # No retries remaining
            # ----------------------------------------------

            if attempt >= GROQ_MAX_RETRIES:

                break

            # ----------------------------------------------
            # Exponential backoff
            # ----------------------------------------------

            delay = _retry_delay(
                attempt
            )

            print(
                f"[Groq] Temporary error "
                f"(attempt {attempt + 1}/"
                f"{GROQ_MAX_RETRIES + 1}). "
                f"Retrying in {delay:.1f}s..."
            )

            time.sleep(delay)

    # --------------------------------------------------------
    # All retries failed
    # --------------------------------------------------------

    print(
        "[Groq] Extraction failed after retries:",
        str(last_error)[:500],
    )

    return []


# ============================================================
# EXTRACT COMPLETE PDF
# ============================================================

def extract_rules_from_text(
    full_text: str,
    pages_per_chunk: int = 1,
) -> List[Dict[str, Any]]:
    """
    Split extracted PDF text into page-based chunks
    and run LLM extraction on each chunk.

    Default:
        1 page per LLM request

    This keeps requests small enough for Groq TPM limits.
    """

    from app.services.pdf_extractor import (
    chunk_relevant_policy_pages
)

    if not full_text:
        return []

    all_rules: List[
        Dict[str, Any]
    ] = []

    chunks = chunk_relevant_policy_pages(
    full_text,
    pages_per_chunk=pages_per_chunk,
    min_score=1
)

    total_chunks = len(chunks)

    print(
        f"[Policy Extraction] "
        f"Processing {total_chunks} chunk(s) "
        f"using {pages_per_chunk} page(s) per request."
    )

    for index, (
        chunk_text,
        start_page,
        end_page,
    ) in enumerate(
        chunks,
        start=1,
    ):

        print(
            f"[Policy Extraction] "
            f"Chunk {index}/{total_chunks} "
            f"(pages {start_page}-{end_page})"
        )

        try:

            rules = extract_rules_from_chunk(
                chunk_text
            )

            # ----------------------------------------------
            # Normalize page information
            # ----------------------------------------------

            for rule in rules:

                if not isinstance(
                    rule,
                    dict,
                ):
                    continue

                # If the model did not provide a page,
                # use the chunk's starting page.
                if not rule.get(
                    "source_page"
                ):
                    rule[
                        "source_page"
                    ] = str(
                        start_page or ""
                    )

                # Ensure source text exists.
                if not rule.get(
                    "source_text"
                ):
                    rule[
                        "source_text"
                    ] = ""

                all_rules.append(
                    rule
                )

        except Exception as e:

            # ------------------------------------------------
            # IMPORTANT:
            #
            # Do NOT insert DOCUMENTATION_MISSING here.
            #
            # That would make an API failure look like a
            # legitimate insurance rule.
            # ------------------------------------------------

            print(
                f"[Policy Extraction] "
                f"Failed for pages "
                f"{start_page}-{end_page}: "
                f"{str(e)[:500]}"
            )

            continue

        # ----------------------------------------------------
        # Small delay between successful requests.
        #
        # This helps avoid hitting TPM/RPM limits when a
        # 45-page document generates many sequential requests.
        # ----------------------------------------------------

        if index < total_chunks:

            time.sleep(
                GROQ_RETRY_BASE_DELAY
            )

    print(
        f"[Policy Extraction] "
        f"Completed. "
        f"Extracted {len(all_rules)} rule(s)."
    )

    return all_rules