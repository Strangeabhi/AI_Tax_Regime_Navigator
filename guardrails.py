"""
Guardrails for the AI Tax Regime Navigator.
- Query blocking: block tax evasion, fraud, document falsification before they reach the AI
- Input validation (numeric ranges, allowed values)
- Prompt boundaries (no personal advice, no guarantee of accuracy)
- Disclaimer text for UI and model context
"""

import re
from typing import Any

# Allowed states (sample; extend as needed)
ALLOWED_STATES = [
    "andhra pradesh", "bihar", "delhi", "gujarat", "haryana", "karnataka", "kerala",
    "madhya pradesh", "maharashtra", "odisha", "punjab", "rajasthan", "tamil nadu",
    "telangana", "uttar pradesh", "west bengal",
]

MAX_ANNUAL_INCOME = 10_00_00_000  # 1 Cr
MAX_DEDUCTION_80C = 150_000
MAX_DEDUCTION_80D = 50_000
MAX_DEDUCTION_80CCD_1B = 50_000
MAX_DEDUCTION_80TTA = 10_000
MAX_HOME_LOAN_INTEREST = 200_000
MAX_AGE = 120
MIN_AGE = 18

DISCLAIMER = (
    "This tool is for educational and general guidance only. It is not a substitute for "
    "professional tax advice. Always refer to the Income Tax Act, Finance Act, and official "
    "CBDT/Income Tax Portal for authoritative provisions. Consult a qualified CA for your specific situation."
)

# 1️⃣ Query blocking: Requests to evade tax (illegal intent)
# These must be blocked immediately. Guardrail: Refuse + explain legal consequences + redirect to compliance.
BLOCKED_ILLEGAL_PATTERNS = [
    r"\b(evade|evasion|evading)\s+(tax|taxes)\b",
    r"\bhide\s+(income|money|salary|freelance)\b",
    r"\bhide\s+.*\s+from\s+(IT|income\s+tax|department)\b",
    r"\b(black\s+money|unaccounted)\b",
    r"\bfake\s+(invoice|bill|receipt|hra|proof)\b",
    r"\b(conceal|hide)\s+income\b",
    r"\bunderreport(ing)?\s+income\b",
    r"\bhow\s+to\s+(avoid|escape)\s+pay(ing)?\s+tax\b",
    r"\bavoid\s+paying\s+tax\b",
    r"\bavoid\s+paying\s+tax\s+.*without\s+showing\b",
    r"\b(split|transfer)\s+income\s+(across|to|with)\s+family\b",
    r"\bsplit\s+.*income.*reduce\s+tax\b",
    r"\bfake\s+HRA\s+proof\b",
    r"\bhow\s+to\s+avoid\s+TDS\b",
    r"\bavoid\s+TDS\b",
    r"\bbribe\b",
    r"\bmoney\s+launder(ing)?\b",
]
BLOCKED_ILLEGAL_RESPONSE = (
    "I can't answer this. Tax evasion, fraud, and document falsification are serious offences "
    "under the Income Tax Act and can result in penalties, prosecution, and imprisonment. "
    "I can only help with legitimate tax regime rules—Old vs New regime, deductions, exemptions, "
    "and compliance. Ask me about legal tax-saving options or regime comparison instead."
)

BLOCKED_OFF_TOPIC_PATTERNS = [
    r"^(what('s|s)\s+the\s+weather|tell\s+me\s+a\s+joke)",
    r"\b(kill|suicide|self\s*harm)\b",
    r"\b(recipe|cooking|food)\b",
    r"\b(sports|football|cricket)\b",
]
BLOCKED_OFF_TOPIC_RESPONSE = (
    "I can only help with Indian income tax regime questions—Old vs New regime, deductions, "
    "exemptions, eligibility, and compliance. Please ask something related to income tax."
)

SYSTEM_GUARDRAIL = (
    "You are an Indian income tax guidance assistant. You must: "
    "1) Base explanations on the provided official provisions only. "
    "2) Not guarantee tax outcomes or suggest illegal tax evasion. "
    "3) Recommend consulting a CA for personal decisions. "
    "4) Clearly state when something is a simplification or subject to conditions. "
    "5) Flag common misinterpretations (e.g. claiming 80C/80D in New Regime). "
    "Do not provide personal financial or legal advice; only explain rules and options."
)


def _to_number(value: Any, default: float = 0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def validate_and_sanitize_inputs(data: dict) -> tuple[dict, list[str]]:
    """
    Validate and sanitize user inputs. Returns (sanitized_data, list of warning messages).
    """
    warnings = []
    out = {}

    # Income
    annual = _to_number(data.get("annual_income"))
    if annual < 0:
        annual = 0
        warnings.append("Annual income was negative; treated as 0.")
    if annual > MAX_ANNUAL_INCOME:
        warnings.append(f"Annual income capped at ₹{MAX_ANNUAL_INCOME:.0f} for this calculator.")
        annual = MAX_ANNUAL_INCOME
    out["annual_income"] = annual

    out["income_from_interest"] = max(0, _to_number(data.get("income_from_interest")))
    out["income_from_other_sources"] = max(0, _to_number(data.get("income_from_other_sources")))

    # Deductions – cap at legal limits
    out["section_80c"] = min(max(0, _to_number(data.get("section_80c"))), MAX_DEDUCTION_80C)
    out["section_80d"] = min(max(0, _to_number(data.get("section_80d"))), MAX_DEDUCTION_80D)
    out["section_80ccd_1b"] = min(max(0, _to_number(data.get("section_80ccd_1b"))), MAX_DEDUCTION_80CCD_1B)
    out["section_80tta"] = min(max(0, _to_number(data.get("section_80tta"))), MAX_DEDUCTION_80TTA)
    out["home_loan_interest"] = min(max(0, _to_number(data.get("home_loan_interest"))), MAX_HOME_LOAN_INTEREST)

    # HRA
    out["hra_received"] = max(0, _to_number(data.get("hra_received")))
    out["rent_paid"] = max(0, _to_number(data.get("rent_paid")))

    # Age
    age = int(_to_number(data.get("age"), 30))
    if age < MIN_AGE or age > MAX_AGE:
        warnings.append(f"Age should be between {MIN_AGE} and {MAX_AGE}; using 30 for calculations.")
        age = max(MIN_AGE, min(MAX_AGE, age))
    out["age"] = age

    # State – normalize
    state = (data.get("state") or "Delhi").strip()
    if state.lower() not in ALLOWED_STATES:
        state = "Delhi"
        warnings.append("State not in list; using Delhi for Professional Tax.")
    out["state"] = state

    # City type
    ct = (data.get("city_type") or "Non-Metro").strip()
    if ct.lower() not in ("metro", "non-metro"):
        ct = "Non-Metro"
    out["city_type"] = ct

    return out, warnings


def should_block_query(query: str) -> tuple[bool, str | None]:
    """
    Check if user query should be blocked (tax evasion, fraud, off-topic).
    Returns (blocked, response_message). If blocked=True, show response and do NOT send to AI.
    """
    if not query or not query.strip():
        return True, "Please enter a question related to Indian income tax."

    q = query.strip()

    for pat in BLOCKED_ILLEGAL_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            return True, BLOCKED_ILLEGAL_RESPONSE

    for pat in BLOCKED_OFF_TOPIC_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            return True, BLOCKED_OFF_TOPIC_RESPONSE

    return False, None


def get_disclaimer() -> str:
    return DISCLAIMER


def get_system_guardrail() -> str:
    return SYSTEM_GUARDRAIL
