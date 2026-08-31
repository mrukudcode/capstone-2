"""
Deterministic financial calculator for the pre-submission
health-insurance claim validator.

IMPORTANT
---------
This module performs arithmetic only.

It does NOT:
    - call an LLM
    - predict insurer approval
    - predict insurer rejection
    - guarantee an insurer payout
    - make legal/medical decisions

All financial adjustments must come from deterministic rule
evaluators.

The calculation is a RULE-BASED ESTIMATE and must be reviewed
against the applicable policy wording before being relied upon.
"""

from decimal import Decimal, InvalidOperation


# ================================================================
# CONSTANTS
# ================================================================

ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")


# ================================================================
# DECIMAL HELPERS
# ================================================================

def _decimal(value, default=ZERO):
    """
    Safely convert a value to Decimal.

    Handles:
        None
        int
        float
        Decimal
        "1000"
        "Rs.1000"
        "Rs. 1000"
        "₹1000"
        "1,000"
    """

    if value is None:
        return default

    if isinstance(value, Decimal):
        return value

    try:
        text = str(value).strip()

        if not text:
            return default

        text = (
            text
            .replace("₹", "")
            .replace("Rs.", "")
            .replace("Rs", "")
            .replace(",", "")
            .strip()
        )

        return Decimal(text)

    except (
        InvalidOperation,
        ValueError,
        TypeError,
    ):
        return default


def _non_negative(value):
    """
    Prevent negative financial values.
    """

    value = _decimal(value)

    return max(
        value,
        ZERO,
    )


def _clamp(value, minimum=ZERO, maximum=None):
    """
    Clamp a Decimal to a specified range.
    """

    value = _decimal(value)

    if value < minimum:
        value = minimum

    if maximum is not None and value > maximum:
        value = maximum

    return value


# ================================================================
# AMOUNT EXTRACTION
# ================================================================

def _extract_amount(text):
    """
    Extract the first monetary amount from a string.

    Examples:

        "Rs.5000"
        "Rs. 5000"
        "₹5000"
        "Deduct Rs.5000"
        "Patient pays Rs. 2500"

    Returns:
        Decimal
    """

    if text is None:
        return ZERO

    text = str(text)

    text = (
        text
        .replace(",", "")
        .replace("₹", "Rs.")
    )

    for currency in (
        "Rs.",
        "Rs",
    ):

        if currency not in text:
            continue

        after = text.split(
            currency,
            1,
        )[1].strip()

        number = ""

        decimal_seen = False

        for char in after:

            if char.isdigit():

                number += char

            elif char == "." and not decimal_seen:

                number += char
                decimal_seen = True

            else:

                break

        if number in (
            "",
            ".",
        ):
            continue

        return _non_negative(
            _decimal(number)
        )

    return ZERO


# ================================================================
# SUB-LIMIT ADJUSTMENT
# ================================================================

def _calculate_sublimit_adjustment(
    sublimit_results,
):
    """
    Calculate deterministic sub-limit deductions.

    Expected evaluator output:

        severity = PARTIAL_DEDUCTION

        expected = "... Rs.X ..."
        actual   = "... Rs.Y ..."

    where:

        Y = billed amount
        X = allowed amount

    Adjustment:

        max(Y - X, 0)
    """

    total = ZERO
    breakdown = []

    for item in sublimit_results or []:

        if not isinstance(item, dict):
            continue

        if item.get("severity") != "PARTIAL_DEDUCTION":
            continue

        actual = item.get(
            "actual",
            "",
        )

        expected = item.get(
            "expected",
            "",
        )

        billed = _extract_amount(
            actual
        )

        allowed = _extract_amount(
            expected
        )

        if billed <= ZERO:
            continue

        adjustment = max(
            billed - allowed,
            ZERO,
        )

        total += adjustment

        breakdown.append({
            "rule_id": item.get(
                "rule_id"
            ),
            "billed_amount": str(
                billed
            ),
            "allowed_amount": str(
                allowed
            ),
            "adjustment": str(
                adjustment
            ),
        })

    return (
        total,
        breakdown,
    )


# ================================================================
# DEDUCTIBLE
# ================================================================

def _calculate_deductible(
    deductible_results,
):
    """
    Calculate deductible from deterministic evaluator output.

    Example:

        expected = "Deduct Rs.5000"
    """

    total = ZERO
    breakdown = []

    for item in deductible_results or []:

        if not isinstance(item, dict):
            continue

        if item.get("severity") != "PARTIAL_DEDUCTION":
            continue

        expected = item.get(
            "expected",
            "",
        )

        amount = _extract_amount(
            expected
        )

        if amount <= ZERO:
            continue

        total += amount

        breakdown.append({
            "rule_id": item.get(
                "rule_id"
            ),
            "deductible": str(
                amount
            ),
        })

    return (
        total,
        breakdown,
    )


# ================================================================
# CO-PAYMENT
# ================================================================

def _extract_percentage(
    result,
):
    """
    Extract a percentage from evaluator output.

    Searches:

        actual
        expected
        reason
    """

    if not isinstance(result, dict):
        return None

    for field in (
        "actual",
        "expected",
        "reason",
    ):

        value = result.get(
            field,
            "",
        )

        if not value:
            continue

        text = str(value)

        if "%" not in text:
            continue

        before_percent = text.split(
            "%",
            1,
        )[0]

        number = ""

        for char in reversed(
            before_percent
        ):

            if char.isdigit() or char == ".":

                number = (
                    char
                    + number
                )

            elif number:

                break

        if not number:
            continue

        try:

            return _clamp(
                Decimal(number),
                ZERO,
                ONE_HUNDRED,
            )

        except InvalidOperation:

            continue

    return None


def _calculate_copay(
    copay_results,
    eligible_before_copay,
):
    """
    Calculate co-payment.

    Prefer an evaluator-computed monetary amount.

    Otherwise calculate:

        eligible_before_copay * copay% / 100
    """

    total = ZERO
    breakdown = []

    eligible_before_copay = _non_negative(
        eligible_before_copay
    )

    for item in copay_results or []:

        if not isinstance(item, dict):
            continue

        if item.get("severity") != "PARTIAL_DEDUCTION":
            continue

        # --------------------------------------------------------
        # 1. Prefer explicit monetary amount.
        # --------------------------------------------------------

        explicit_amount = _extract_amount(
            item.get(
                "actual",
                "",
            )
        )

        if explicit_amount > ZERO:

            amount = min(
                explicit_amount,
                eligible_before_copay,
            )

            total += amount

            breakdown.append({
                "rule_id": item.get(
                    "rule_id"
                ),
                "method": "evaluator_amount",
                "copay_amount": str(
                    amount
                ),
            })

            continue

        # --------------------------------------------------------
        # 2. Otherwise calculate from percentage.
        # --------------------------------------------------------

        percentage = _extract_percentage(
            item
        )

        if percentage is None:
            continue

        copay = (
            eligible_before_copay
            * percentage
            / ONE_HUNDRED
        )

        copay = min(
            copay,
            eligible_before_copay,
        )

        total += copay

        breakdown.append({
            "rule_id": item.get(
                "rule_id"
            ),
            "method": "percentage",
            "percentage": str(
                percentage
            ),
            "copay_amount": str(
                copay
            ),
        })

    return (
        total,
        breakdown,
    )


# ================================================================
# ROOM RENT
# ================================================================

def _calculate_room_rent_adjustment(
    room_rent_adjustment_results,
):
    """
    Process deterministic room-rent results.

    IMPORTANT
    ---------
    A room-rent rule may provide an admissible fraction without
    providing a policy-authorized rupee deduction from the entire
    claim.

    Therefore this function distinguishes:

        exact monetary adjustment
        calculated admissible fraction
        unresolved financial impact

    We NEVER convert the admissible fraction into a deduction from
    the entire hospital bill unless the evaluator explicitly
    provides a monetary adjustment.
    """

    exact_adjustment = ZERO

    exact = True

    breakdown = []

    for item in (
        room_rent_adjustment_results or []
    ):

        if not isinstance(item, dict):
            continue

        severity = item.get(
            "severity"
        )

        if severity != "PARTIAL_DEDUCTION":
            continue

        actual = str(
            item.get(
                "actual",
                ""
            )
        )

        expected = str(
            item.get(
                "expected",
                ""
            )
        )

        # --------------------------------------------------------
        # 1. Explicit monetary adjustment.
        # --------------------------------------------------------

        explicit_adjustment = ZERO

        for field in (
            "deduction_amount",
            "adjustment_amount",
            "amount",
        ):

            if field not in item:
                continue

            candidate = _non_negative(
                item.get(field)
            )

            if candidate > ZERO:

                explicit_adjustment = candidate
                break

        # --------------------------------------------------------
        # 2. Calculate room-rent excess if possible.
        #
        # This is NOT automatically deducted from the entire
        # hospital bill.
        # --------------------------------------------------------

        actual_room_rent = _extract_amount(
            actual
        )

        allowed_room_rent = _extract_amount(
            expected
        )

        room_rent_excess = ZERO

        if (
            actual_room_rent > ZERO
            and allowed_room_rent > ZERO
        ):

            room_rent_excess = max(
                actual_room_rent
                - allowed_room_rent,
                ZERO,
            )

        # --------------------------------------------------------
        # 3. Try to identify admissible fraction.
        #
        # The updated room_rent.py describes it in the reason:
        #
        # "admissible room-rent fraction is 0.8000"
        #
        # We deliberately do NOT use that fraction against the
        # whole claim unless a policy-specific evaluator provides
        # an exact monetary adjustment.
        # --------------------------------------------------------

        admissible_fraction = None

        if (
            actual_room_rent > ZERO
            and allowed_room_rent > ZERO
        ):

            admissible_fraction = (
                allowed_room_rent
                / actual_room_rent
            )

            admissible_fraction = _clamp(
                admissible_fraction,
                ZERO,
                Decimal("1"),
            )

        # --------------------------------------------------------
        # 4. Determine exactness.
        # --------------------------------------------------------

        if explicit_adjustment > ZERO:

            exact_adjustment += (
                explicit_adjustment
            )

            breakdown.append({

                "rule_id": item.get(
                    "rule_id"
                ),

                "adjustment": str(
                    explicit_adjustment
                ),

                "exact": True,

                "method": (
                    "explicit_evaluator_amount"
                ),

                "expected": expected,

                "actual": actual,

            })

        else:

            exact = False

            breakdown.append({

                "rule_id": item.get(
                    "rule_id"
                ),

                "adjustment": "0",

                "exact": False,

                "method": (
                    "admissible_fraction_only"
                ),

                "room_rent_excess": str(
                    room_rent_excess
                ),

                "admissible_fraction": (
                    str(admissible_fraction)
                    if admissible_fraction
                    is not None
                    else None
                ),

                "expected": expected,

                "actual": actual,

                "note": (
                    "Room-rent limit was exceeded, "
                    "but no policy-authorized monetary "
                    "deduction for the entire claim was "
                    "provided. No claim-wide deduction "
                    "was invented."
                ),
            })

    return (
        exact_adjustment,
        exact,
        breakdown,
    )


# ================================================================
# MAIN CALCULATOR
# ================================================================

def calculate_financials(
    billed_amount,
    room_rent_adjustment_results,
    sublimit_results,
    deductible_results,
    copay_results,
):
    """
    Calculate the deterministic financial estimate.

    Calculation order:

        1. Gross billed amount
        2. Explicit room-rent monetary adjustment
        3. Sub-limit adjustment
        4. Deductible
        5. Co-payment
        6. Estimated eligible amount

    IMPORTANT
    ---------
    Room-rent proportional consequences are NOT automatically
    applied to the whole claim.

    If the room-rent evaluator only provides an admissible fraction,
    the result is flagged as PARTIAL_CALCULATION.

    This prevents the system from inventing a rupee deduction that
    is not explicitly supported by the extracted policy rule.
    """

    # ============================================================
    # 1. GROSS BILL
    # ============================================================

    gross_bill = _non_negative(
        billed_amount
    )

    remaining = gross_bill

    # ============================================================
    # 2. ROOM RENT
    # ============================================================

    (
        room_rent_adjustment,
        room_rent_exact,
        room_rent_breakdown,
    ) = _calculate_room_rent_adjustment(
        room_rent_adjustment_results
    )

    room_rent_adjustment = min(
        room_rent_adjustment,
        remaining,
    )

    remaining -= room_rent_adjustment

    remaining = max(
        remaining,
        ZERO,
    )

    # ============================================================
    # 3. SUB-LIMIT
    # ============================================================

    (
        sublimit_adjustment,
        sublimit_breakdown,
    ) = _calculate_sublimit_adjustment(
        sublimit_results
    )

    sublimit_adjustment = min(
        sublimit_adjustment,
        remaining,
    )

    remaining -= sublimit_adjustment

    remaining = max(
        remaining,
        ZERO,
    )

    # ============================================================
    # 4. DEDUCTIBLE
    # ============================================================

    (
        deductible_amount,
        deductible_breakdown,
    ) = _calculate_deductible(
        deductible_results
    )

    deductible_amount = min(
        deductible_amount,
        remaining,
    )

    remaining -= deductible_amount

    remaining = max(
        remaining,
        ZERO,
    )

    # ============================================================
    # 5. CO-PAY
    # ============================================================

    (
        copay_amount,
        copay_breakdown,
    ) = _calculate_copay(
        copay_results,
        remaining,
    )

    copay_amount = min(
        copay_amount,
        remaining,
    )

    remaining -= copay_amount

    remaining = max(
        remaining,
        ZERO,
    )

    # ============================================================
    # 6. TOTAL ADJUSTMENT
    # ============================================================

    total_adjustment = (
        room_rent_adjustment
        + sublimit_adjustment
        + deductible_amount
        + copay_amount
    )

    total_adjustment = min(
        total_adjustment,
        gross_bill,
    )

    # ============================================================
    # 7. ESTIMATED ELIGIBLE AMOUNT
    # ============================================================

    estimated_eligible_amount = max(
        gross_bill
        - total_adjustment,
        ZERO,
    )

    # ============================================================
    # 8. CALCULATION STATUS
    # ============================================================

    if not room_rent_exact:

        calculation_status = (
            "PARTIAL_CALCULATION"
        )

        calculation_note = (
            "A room-rent limit was exceeded, but the "
            "deterministic evaluator provided only the "
            "room-rent admissible fraction and not a "
            "policy-authorized monetary deduction against "
            "the complete claim. The system therefore does "
            "not invent a claim-wide room-rent deduction. "
            "Human review of the applicable proportionate-"
            "deduction clause is required."
        )

    else:

        calculation_status = (
            "CALCULATED"
        )

        calculation_note = (
            "All financial adjustments included in the "
            "estimated eligible amount were supported by "
            "deterministic monetary calculations."
        )

    # ============================================================
    # 9. RETURN RESULT
    # ============================================================

    return {

        "label": (
            "RULE-BASED ESTIMATE -- "
            "NOT A GUARANTEED INSURER PAYOUT"
        ),

        "status": calculation_status,

        "calculation_note": calculation_note,

        "calculation_order": [
            "gross_bill",
            "room_rent_adjustment",
            "sub_limit_adjustment",
            "deductible",
            "copay_amount",
            "estimated_eligible_amount",
        ],

        # --------------------------------------------------------
        # Main financial amounts
        # --------------------------------------------------------

        "gross_bill": str(
            gross_bill
        ),

        "room_rent_adjustment": str(
            room_rent_adjustment
        ),

        "sub_limit_adjustment": str(
            sublimit_adjustment
        ),

        "deductible": str(
            deductible_amount
        ),

        "copay_amount": str(
            copay_amount
        ),

        "total_adjustment": str(
            total_adjustment
        ),

        "estimated_eligible_amount": str(
            estimated_eligible_amount
        ),

        # --------------------------------------------------------
        # Detailed breakdown
        # --------------------------------------------------------

        "breakdown": {

            "room_rent": {

                "adjustment": str(
                    room_rent_adjustment
                ),

                "exact": room_rent_exact,

                "rules": room_rent_breakdown,

            },

            "sub_limits": {

                "adjustment": str(
                    sublimit_adjustment
                ),

                "rules": sublimit_breakdown,

            },

            "deductible": {

                "amount": str(
                    deductible_amount
                ),

                "rules": deductible_breakdown,

            },

            "copay": {

                "amount": str(
                    copay_amount
                ),

                "rules": copay_breakdown,

            },

        },

        # --------------------------------------------------------
        # Safety / interpretation
        # --------------------------------------------------------

        "disclaimer": (
            "This is a deterministic rule-based estimate "
            "derived from extracted policy rules and supplied "
            "claim data. It is not a guaranteed insurer payout. "
            "Room-rent proportional deductions are not applied "
            "to the complete claim unless an applicable "
            "deterministic evaluator provides an explicit "
            "policy-supported monetary adjustment."
        ),
    }