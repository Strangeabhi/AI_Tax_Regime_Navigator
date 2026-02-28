"""
Tax calculation engine for Old and New regime (India FY 2024-25 / AY 2025-26).
Used by the AI Tax Regime Navigator for computations only; explanations come from RAG + LLM.
"""


def get_professional_tax(state: str, gross_income: float) -> float:
    """Annual Professional Tax based on State and Gross Income (simplified)."""
    state = state.lower().strip()
    high_pt_states = [
        "maharashtra", "karnataka", "telangana", "andhra pradesh",
        "west bengal", "tamil nadu", "gujarat", "madhya pradesh", "kerala", "odisha"
    ]
    if state in high_pt_states:
        if gross_income > 150000:
            return 2500
        if gross_income > 100000:
            return 2000
    return 0


def calculate_tax_old_regime(data: dict) -> dict:
    """Compute tax under Old Regime with deductions (80C, 80D, 80CCD(1B), 80TTA, 24(b), HRA, Standard Deduction)."""
    salary = float(data.get("annual_income", 0) or 0)
    interest = float(data.get("income_from_interest", 0) or 0)
    other = float(data.get("income_from_other_sources", 0) or 0)
    gross_income = salary + interest + other

    prof_tax = get_professional_tax(data.get("state", "Delhi"), gross_income)

    ded_80c = min(float(data.get("section_80c", 0) or 0), 150000)
    ded_80d = min(float(data.get("section_80d", 0) or 0), 25000)
    ded_80ccd_1b = min(float(data.get("section_80ccd_1b", 0) or 0), 50000)
    ded_80tta = min(float(data.get("section_80tta", 0) or 0), 10000)
    home_loan_interest = min(float(data.get("home_loan_interest", 0) or 0), 200000)

    std_deduction = 50000
    hra_exemption = 0
    hra_received = float(data.get("hra_received", 0) or 0)
    rent_paid = float(data.get("rent_paid", 0) or 0)
    if hra_received > 0 and rent_paid > 0 and salary > 0:
        actual_hra = hra_received
        rent_minus_10 = max(0, rent_paid - 0.10 * salary)
        is_metro = (data.get("city_type") or "").strip().lower() == "metro"
        limit_pct = 0.50 if is_metro else 0.40
        hra_limit = limit_pct * salary
        hra_exemption = min(actual_hra, rent_minus_10, hra_limit)

    total_deductions = (
        std_deduction + prof_tax + ded_80c + ded_80d + ded_80ccd_1b
        + ded_80tta + home_loan_interest + hra_exemption
    )
    taxable_income = max(0, gross_income - total_deductions)

    # Old regime slabs
    if taxable_income <= 250000:
        base_tax = 0
    elif taxable_income <= 500000:
        base_tax = (taxable_income - 250000) * 0.05
    elif taxable_income <= 1000000:
        base_tax = 12500 + (taxable_income - 500000) * 0.20
    else:
        base_tax = 112500 + (taxable_income - 1000000) * 0.30

    if taxable_income <= 500000:
        base_tax = 0  # Rebate 87A

    cess = base_tax * 0.04
    total_tax = base_tax + cess

    return {
        "regime": "Old Regime",
        "gross_income": round(gross_income, 2),
        "total_deductions": round(total_deductions, 2),
        "taxable_income": round(taxable_income, 2),
        "base_tax": round(base_tax, 2),
        "cess": round(cess, 2),
        "total_tax_payable": round(total_tax, 2),
        "components": {
            "Standard Deduction": std_deduction,
            "80C": ded_80c,
            "80D": ded_80d,
            "80CCD(1B) (NPS)": ded_80ccd_1b,
            "80TTA": ded_80tta,
            "HRA Exemption": round(hra_exemption, 2),
            "Home Loan Interest (24(b))": home_loan_interest,
            "Professional Tax": prof_tax,
        },
    }


def calculate_tax_new_regime(data: dict) -> dict:
    """Compute tax under New Regime (Standard Deduction only for salaried)."""
    salary = float(data.get("annual_income", 0) or 0)
    interest_income = float(data.get("income_from_interest", 0) or 0)
    other_income = float(data.get("income_from_other_sources", 0) or 0)
    gross_income = salary + interest_income + other_income

    std_deduction = 50000 if salary > 0 else 0
    total_deductions = std_deduction
    taxable_income = max(0, gross_income - total_deductions)

    # New regime slabs
    if taxable_income <= 300000:
        base_tax = 0
    elif taxable_income <= 600000:
        base_tax = (taxable_income - 300000) * 0.05
    elif taxable_income <= 900000:
        base_tax = 15000 + (taxable_income - 600000) * 0.10
    elif taxable_income <= 1200000:
        base_tax = 45000 + (taxable_income - 900000) * 0.15
    elif taxable_income <= 1500000:
        base_tax = 90000 + (taxable_income - 1200000) * 0.20
    else:
        base_tax = 150000 + (taxable_income - 1500000) * 0.30

    if taxable_income <= 700000:
        base_tax = 0  # Rebate 87A New Regime

    cess = base_tax * 0.04
    total_tax = base_tax + cess

    return {
        "regime": "New Regime",
        "gross_income": round(gross_income, 2),
        "total_deductions": round(total_deductions, 2),
        "taxable_income": round(taxable_income, 2),
        "base_tax": round(base_tax, 2),
        "cess": round(cess, 2),
        "total_tax_payable": round(total_tax, 2),
    }


def calculate_comprehensive(data: dict) -> dict:
    """Compute both regimes and return comparison + best regime and suggestions."""
    old_r = calculate_tax_old_regime(data)
    new_r = calculate_tax_new_regime(data)
    best = "New Regime" if new_r["total_tax_payable"] < old_r["total_tax_payable"] else "Old Regime"
    tax_saved = abs(old_r["total_tax_payable"] - new_r["total_tax_payable"])

    suggestions = []
    if (data.get("section_80c") or 0) < 150000:
        gap = 150000 - (data.get("section_80c") or 0)
        suggestions.append(f"Invest ₹{gap:,.0f} more in 80C (PPF, ELSS, LIC) to save tax in Old Regime.")
    if (data.get("section_80ccd_1b") or 0) < 50000:
        gap = 50000 - (data.get("section_80ccd_1b") or 0)
        suggestions.append(f"Invest ₹{gap:,.0f} in NPS (80CCD(1B)) for extra deduction in Old Regime.")
    if (data.get("section_80d") or 0) == 0:
        suggestions.append("Consider Health Insurance (80D) for yourself/parents if you choose Old Regime.")

    return {
        "old_regime": old_r,
        "new_regime": new_r,
        "best_regime": best,
        "tax_saved": round(tax_saved, 2),
        "suggestions": suggestions,
    }
