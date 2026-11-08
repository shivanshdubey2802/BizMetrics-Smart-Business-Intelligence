"""SIH 26091 financing rules and quarterly repayment calculations."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

MICRO_FINANCE = "Micro Finance"
TERM_LOAN = "Term Loan"
UNSUPPORTED = "Unsupported"
MAX_PROJECT_COST = 5_000_000.0
MICRO_PROJECT_LIMIT = 140_000.0


def financing_capacity(available_margin: float) -> dict[str, float]:
    margin = max(0.0, float(available_margin or 0))
    maximum_project_cost = margin * 10.0
    return {
        "available_margin": margin,
        "maximum_project_cost": maximum_project_cost,
        "required_margin": maximum_project_cost * 0.10,
        "maximum_loan": maximum_project_cost * 0.90,
    }


def select_scheme(project_cost: float) -> dict[str, Any]:
    cost = float(project_cost or 0)
    if cost < 0:
        return {"name": UNSUPPORTED, "supported": False, "reason": "Project cost cannot be negative."}
    if cost > MAX_PROJECT_COST:
        return {"name": UNSUPPORTED, "supported": False, "reason": "Project cost exceeds the SIH limit of ₹50 lakh."}
    if cost <= MICRO_PROJECT_LIMIT:
        return {
            "name": MICRO_FINANCE,
            "supported": True,
            "interest_rate": 6.5,
            "tenure_years": 3,
            "moratorium_months": 3,
        }
    return {
        "name": TERM_LOAN,
        "supported": True,
        "interest_rate": 8.0,
        "tenure_years": 7,
        "moratorium_months": 6,
    }


def calculate_emi(principal: float, annual_rate: float, tenure_months: int) -> float:
    principal = max(0.0, float(principal or 0))
    months = int(tenure_months or 0)
    rate = max(0.0, float(annual_rate or 0)) / 100.0 / 12.0
    if principal == 0 or months <= 0:
        return 0.0
    if rate == 0:
        return principal / months
    factor = (1 + rate) ** months
    return principal * rate * factor / (factor - 1)


def _period_rate(annual_rate: float) -> float:
    return max(0.0, float(annual_rate or 0)) / 100.0 / 4.0


def build_quarterly_schedule(
    principal: float,
    annual_rate: float,
    tenure_months: int,
    moratorium_months: int,
) -> dict[str, Any]:
    """Build a quarterly schedule with interest-only moratorium periods.

    Interest treatment is intentionally explicit: moratorium payments cover
    accrued interest while principal remains unchanged. The schedule rounds only
    the final payment so principal conservation remains exact within tolerance.
    """
    original = max(0.0, float(principal or 0))
    months = int(tenure_months or 0)
    moratorium = max(0, int(moratorium_months or 0))
    if months <= 0 or original == 0:
        return {"schedule": pd.DataFrame(), "quarterly_payment": 0.0, "valid": original == 0}
    moratorium = min(moratorium, months)
    total_quarters = max(1, math.ceil(months / 3))
    moratorium_quarters = min(total_quarters, math.ceil(moratorium / 3))
    repayment_quarters = total_quarters - moratorium_quarters
    rate = _period_rate(annual_rate)
    balance = original
    rows: list[dict[str, Any]] = []

    repayment_payment = 0.0
    if repayment_quarters > 0:
        if rate == 0:
            repayment_payment = balance / repayment_quarters
        else:
            factor = (1 + rate) ** repayment_quarters
            repayment_payment = balance * rate * factor / (factor - 1)

    cumulative_interest = 0.0
    cumulative_repayment = 0.0
    for quarter in range(1, total_quarters + 1):
        opening = balance
        interest = opening * rate
        if quarter <= moratorium_quarters:
            principal_repaid = 0.0
            payment = interest
            closing = opening
            status = "MORATORIUM"
        else:
            principal_repaid = min(opening, max(0.0, repayment_payment - interest))
            closing = max(0.0, opening - principal_repaid)
            payment = interest + principal_repaid
            status = "REPAYMENT"
            if quarter == total_quarters:
                principal_repaid = opening
                payment = interest + principal_repaid
                closing = 0.0
        cumulative_interest += interest
        cumulative_repayment += payment
        rows.append({
            "Quarter": f"Q{quarter}",
            "Period": f"Months {(quarter - 1) * 3 + 1} to {min(quarter * 3, months)}",
            "Opening Principal": opening,
            "Interest": interest,
            "Principal Repaid": principal_repaid,
            "Total Payment": payment,
            "Closing Principal": closing,
            "Cumulative Interest": cumulative_interest,
            "Cumulative Repayment": cumulative_repayment,
            "Status": status,
        })
        balance = closing

    schedule = pd.DataFrame(rows)
    total_principal = float(schedule["Principal Repaid"].sum()) if not schedule.empty else 0.0
    total_interest = float(schedule["Interest"].sum()) if not schedule.empty else 0.0
    total_repayment = float(schedule["Total Payment"].sum()) if not schedule.empty else 0.0
    continuity = schedule.empty or all(
        abs(schedule.iloc[index]["Opening Principal"] - schedule.iloc[index - 1]["Closing Principal"]) < 0.01
        for index in range(1, len(schedule))
    )
    moratorium_valid = schedule.empty or (schedule.loc[schedule["Status"] == "MORATORIUM", "Principal Repaid"].abs() < 0.01).all()
    valid = (
        abs(total_principal - original) < 0.01
        and abs(total_repayment - total_principal - total_interest) < 0.01
        and abs(balance) < 0.01
        and (schedule.empty or (schedule["Closing Principal"] >= -0.01).all())
        and continuity
        and moratorium_valid
    )
    return {
        "schedule": schedule,
        "quarterly_payment": repayment_payment,
        "total_principal": total_principal,
        "total_interest": total_interest,
        "total_repayment": total_repayment,
        "final_balance": balance,
        "valid": bool(valid),
        "moratorium_quarters": moratorium_quarters,
    }
