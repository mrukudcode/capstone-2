import sys

sys.path.insert(0, "backend")

from app.services.llm_rule_extractor import extract_rules


policy_text = """
Room Rent Criteria:

For Sum Insured of Rs. 5 Lakhs and Rs. 7.5 Lakhs,
Room Rent is limited to 1% of Sum Insured per day.

For Sum Insured of Rs. 10 Lakhs and above,
Any Room can be opted.

Co-payment:

Insured persons aged 61 years and above at the time
of entry shall bear 10% of the admissible claim amount
as co-payment.
"""


rules = extract_rules(policy_text)

print("\nEXTRACTED RULES\n")
print("=" * 80)

for i, rule in enumerate(rules, 1):
    print(f"\nRULE {i}")
    print("-" * 40)

    for key, value in rule.items():
        print(f"{key}: {value}")