"""
AI Current Tax Regime Navigator – Streamlit app.
Helps users understand Old vs New tax regime, compare outcomes, and get RAG-backed explanations via Groq.
Run: streamlit run app.py (from project root, with venv activated).
"""

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

import streamlit as st
from tax_engine import calculate_comprehensive, calculate_tax_old_regime, calculate_tax_new_regime
from groq_client import chat, is_configured
from rag import retrieve, format_chunks_for_prompt, get_full_context
from guardrails import (
    validate_and_sanitize_inputs,
    should_block_query,
    get_disclaimer,
    get_system_guardrail,
)

st.set_page_config(
    page_title="AI Tax Regime Navigator",
    page_icon="📋",
    layout="wide",
)

st.title("📋 AI Current Tax Regime Navigator")
st.caption("Understand Old vs New regime, compare your tax, and get rule-based guidance. FY 2024-25 / AY 2025-26.")

# Sidebar: inputs
with st.sidebar:
    st.header("Your details")
    age = st.number_input("Age", min_value=18, max_value=120, value=30, step=1)
    state = st.selectbox(
        "State (for Professional Tax)",
        ["Delhi", "Maharashtra", "Karnataka", "Tamil Nadu", "West Bengal", "Gujarat", "Kerala", "Others"],
    )
    city_type = st.radio("City type (for HRA)", ["Non-Metro", "Metro"], horizontal=True)

    st.subheader("Income (₹/year)")
    annual_income = st.number_input("Salary / Business income", min_value=0.0, value=800000.0, step=10000.0)
    income_interest = st.number_input("Interest income", min_value=0.0, value=0.0, step=1000.0)
    income_other = st.number_input("Other income", min_value=0.0, value=0.0, step=1000.0)

    st.subheader("Deductions (Old Regime only)")
    section_80c = st.number_input("80C (max ₹1,50,000)", min_value=0.0, max_value=150000.0, value=150000.0, step=5000.0)
    section_80d = st.number_input("80D Health (max ₹25k/50k)", min_value=0.0, max_value=50000.0, value=25000.0, step=1000.0)
    section_80ccd_1b = st.number_input("80CCD(1B) NPS (max ₹50,000)", min_value=0.0, max_value=50000.0, value=0.0, step=5000.0)
    section_80tta = st.number_input("80TTA Savings interest (max ₹10k)", min_value=0.0, max_value=10000.0, value=0.0, step=1000.0)
    home_loan_interest = st.number_input("Home loan interest 24(b) (max ₹2L)", min_value=0.0, max_value=200000.0, value=0.0, step=5000.0)

    st.subheader("HRA (Old Regime)")
    hra_received = st.number_input("HRA received", min_value=0.0, value=0.0, step=1000.0)
    rent_paid = st.number_input("Rent paid", min_value=0.0, value=0.0, step=1000.0)

# Build input dict
raw = {
    "age": age,
    "annual_income": annual_income,
    "income_from_interest": income_interest,
    "income_from_other_sources": income_other,
    "section_80c": section_80c,
    "section_80d": section_80d,
    "section_80ccd_1b": section_80ccd_1b,
    "section_80tta": section_80tta,
    "home_loan_interest": home_loan_interest,
    "hra_received": hra_received,
    "rent_paid": rent_paid,
    "state": state if state != "Others" else "Delhi",
    "city_type": city_type,
}

data, validation_warnings = validate_and_sanitize_inputs(raw)
for w in validation_warnings:
    st.sidebar.warning(w)

# Calculate
result = calculate_comprehensive(data)
old_r = result["old_regime"]
new_r = result["new_regime"]
best = result["best_regime"]
tax_saved = result["tax_saved"]
suggestions = result["suggestions"]

# Main: comparison
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Old Regime tax", f"₹{old_r['total_tax_payable']:,.0f}")
    st.caption(f"Taxable income: ₹{old_r['taxable_income']:,.0f}")
with col2:
    st.metric("New Regime tax", f"₹{new_r['total_tax_payable']:,.0f}")
    st.caption(f"Taxable income: ₹{new_r['taxable_income']:,.0f}")
with col3:
    st.metric("Better for you", best)
    if tax_saved > 0:
        st.success(f"Tax difference: ₹{tax_saved:,.0f}")

st.subheader("Breakdown")
tab_old, tab_new = st.tabs(["Old Regime", "New Regime"])
with tab_old:
    st.json({
        "Gross income": old_r["gross_income"],
        "Total deductions": old_r["total_deductions"],
        "Taxable income": old_r["taxable_income"],
        "Tax + Cess": old_r["total_tax_payable"],
        "Components": old_r.get("components", {}),
    })
with tab_new:
    st.json({
        "Gross income": new_r["gross_income"],
        "Total deductions": new_r["total_deductions"],
        "Taxable income": new_r["taxable_income"],
        "Tax + Cess": new_r["total_tax_payable"],
    })

if suggestions:
    st.subheader("Suggestions (if you choose Old Regime)")
    for s in suggestions:
        st.info(s)

# Ask the AI (RAG + Groq)
st.divider()
st.subheader("Ask about rules & regime choice")
st.caption("Answers are based on official provisions (RAG) and may flag common mistakes.")

if not is_configured():
    st.warning("Set GROQ_API_KEY in .env to use AI explanations.")
    user_question = None
else:
    default_q = "When should I choose Old vs New regime? What are common mistakes?"
    user_question = st.text_input(
        "Your question (e.g. eligibility, deductions, compliance risks)",
        value=default_q,
        key="user_question",
    )

if user_question and is_configured():
    if st.button("Get AI guidance"):
        blocked, block_msg = should_block_query(user_question)
        if blocked:
            st.warning(block_msg)
        else:
            with st.spinner("Retrieving provisions and generating answer..."):
                # RAG: retrieve relevant chunks
                chunks = retrieve(user_question, top_k=5)
                context = format_chunks_for_prompt(chunks) if chunks else get_full_context()
                system = get_system_guardrail()
                user_msg = (
                    "Official provisions (use only these for rules):\n\n" + context + "\n\n"
                    "User question: " + user_question + "\n\n"
                    "User situation summary: "
                    f"Age {data['age']}, Gross income ₹{data['annual_income'] + data['income_from_interest'] + data['income_from_other_sources']:,.0f}, "
                    f"80C ₹{data['section_80c']:,.0f}, 80D ₹{data['section_80d']:,.0f}. "
                    f"Calculated best regime for them: {best}. "
                    "Explain clearly and flag any common misinterpretations or compliance risks."
                )
                try:
                    reply = chat([
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_msg},
                    ])
                    st.markdown(reply)
                except Exception as e:
                    st.error(f"AI request failed: {e}")

# Footer disclaimer
st.divider()
st.caption(get_disclaimer())
