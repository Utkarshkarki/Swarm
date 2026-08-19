"""
Agent Tool Registry
===================
Defines Python-side tool functions and their OpenAI-compatible JSON schemas.

Architecture
------------
* Each tool is a plain Python function that runs locally (no external I/O).
* `BANKER_TOOLS` and `BROKER_TOOLS` export the JSON schema lists to pass to the
  OpenAI `tools=` parameter.
* `execute_tool(name, arguments)` is the single dispatch point called by the
  agentic loop in BaseAgent._llm_with_tools().

BankerAgent tools
-----------------
  calculate_emi          — standard reducing-balance EMI formula
  assess_loan_eligibility — FOIR-based max-loan and down-payment recommendation

BrokerAgent tools
-----------------
  fetch_property_pricing  — city + BHK type → price/sqft + comparable data (mock)
  estimate_rental_yield   — city + property price → rent + gross/net yield (mock)
"""
from __future__ import annotations

import json
import logging
import math
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ── Mock market dataset ────────────────────────────────────────────────────────
# Keyed by (city_slug, bhk_type).  Price in ₹/sqft, rent in ₹/month per sqft.
# Appreciation: annual % YoY.  Comparables: number of active listings used.

_CITY_ALIASES: Dict[str, str] = {
    # full name → slug
    "mumbai": "mumbai", "bombay": "mumbai",
    "pune": "pune", "puna": "pune",
    "bangalore": "bangalore", "bengaluru": "bangalore", "bengaluru": "bangalore",
    "hyderabad": "hyderabad", "hyd": "hyderabad",
    "chennai": "chennai", "madras": "chennai",
    "delhi": "delhi", "new delhi": "delhi",
    "gurgaon": "gurgaon", "gurugram": "gurgaon",
    "noida": "noida",
    "ahmedabad": "ahmedabad",
    "kolkata": "kolkata", "calcutta": "kolkata",
    "jaipur": "jaipur",
    "lucknow": "lucknow",
    "kochi": "kochi", "cochin": "kochi",
    "coimbatore": "coimbatore",
    "indore": "indore",
    "nagpur": "nagpur",
}

# (city_slug, bhk) → {avg_sqft_price, price_low, price_high, monthly_rent_per_sqft, appreciation_yoy, comparables}
_MARKET_DATA: Dict[tuple[str, str], Dict[str, Any]] = {
    # Mumbai
    ("mumbai", "1bhk"): {"avg_sqft_price": 18500, "price_low": 15000, "price_high": 22000, "monthly_rent_per_sqft": 52, "appreciation_yoy": 7.2, "comparables": 312},
    ("mumbai", "2bhk"): {"avg_sqft_price": 16800, "price_low": 14000, "price_high": 20000, "monthly_rent_per_sqft": 45, "appreciation_yoy": 6.8, "comparables": 480},
    ("mumbai", "3bhk"): {"avg_sqft_price": 15200, "price_low": 12500, "price_high": 18500, "monthly_rent_per_sqft": 38, "appreciation_yoy": 6.1, "comparables": 198},
    # Pune
    ("pune", "1bhk"):   {"avg_sqft_price": 7200,  "price_low": 5800,  "price_high": 9000,  "monthly_rent_per_sqft": 22, "appreciation_yoy": 9.1, "comparables": 267},
    ("pune", "2bhk"):   {"avg_sqft_price": 8750,  "price_low": 7000,  "price_high": 10500, "monthly_rent_per_sqft": 24, "appreciation_yoy": 9.4, "comparables": 541},
    ("pune", "3bhk"):   {"avg_sqft_price": 9400,  "price_low": 7800,  "price_high": 11500, "monthly_rent_per_sqft": 26, "appreciation_yoy": 8.8, "comparables": 203},
    # Bangalore
    ("bangalore", "1bhk"): {"avg_sqft_price": 8900, "price_low": 7200, "price_high": 11000, "monthly_rent_per_sqft": 28, "appreciation_yoy": 10.2, "comparables": 389},
    ("bangalore", "2bhk"): {"avg_sqft_price": 9800, "price_low": 8000, "price_high": 12500, "monthly_rent_per_sqft": 30, "appreciation_yoy": 10.5, "comparables": 612},
    ("bangalore", "3bhk"): {"avg_sqft_price": 10500,"price_low": 8500, "price_high": 13500, "monthly_rent_per_sqft": 32, "appreciation_yoy": 9.8, "comparables": 274},
    # Hyderabad
    ("hyderabad", "1bhk"): {"avg_sqft_price": 6800, "price_low": 5500, "price_high": 8500,  "monthly_rent_per_sqft": 20, "appreciation_yoy": 11.3, "comparables": 298},
    ("hyderabad", "2bhk"): {"avg_sqft_price": 7500, "price_low": 6200, "price_high": 9200,  "monthly_rent_per_sqft": 22, "appreciation_yoy": 11.8, "comparables": 487},
    ("hyderabad", "3bhk"): {"avg_sqft_price": 8200, "price_low": 7000, "price_high": 10000, "monthly_rent_per_sqft": 24, "appreciation_yoy": 10.9, "comparables": 195},
    # Chennai
    ("chennai", "1bhk"): {"avg_sqft_price": 7100, "price_low": 5800, "price_high": 8800,  "monthly_rent_per_sqft": 21, "appreciation_yoy": 7.5, "comparables": 221},
    ("chennai", "2bhk"): {"avg_sqft_price": 7900, "price_low": 6500, "price_high": 9600,  "monthly_rent_per_sqft": 23, "appreciation_yoy": 7.9, "comparables": 364},
    ("chennai", "3bhk"): {"avg_sqft_price": 8500, "price_low": 7000, "price_high": 10500, "monthly_rent_per_sqft": 25, "appreciation_yoy": 7.2, "comparables": 142},
    # Delhi
    ("delhi", "1bhk"):   {"avg_sqft_price": 9500,  "price_low": 7800, "price_high": 12000, "monthly_rent_per_sqft": 30, "appreciation_yoy": 6.5, "comparables": 188},
    ("delhi", "2bhk"):   {"avg_sqft_price": 10800, "price_low": 8500, "price_high": 13500, "monthly_rent_per_sqft": 32, "appreciation_yoy": 6.8, "comparables": 295},
    ("delhi", "3bhk"):   {"avg_sqft_price": 12000, "price_low": 9500, "price_high": 15000, "monthly_rent_per_sqft": 35, "appreciation_yoy": 6.2, "comparables": 110},
    # Gurgaon
    ("gurgaon", "1bhk"): {"avg_sqft_price": 11000, "price_low": 9000, "price_high": 13500, "monthly_rent_per_sqft": 33, "appreciation_yoy": 8.1, "comparables": 201},
    ("gurgaon", "2bhk"): {"avg_sqft_price": 12500, "price_low":10000, "price_high": 15500, "monthly_rent_per_sqft": 36, "appreciation_yoy": 8.4, "comparables": 347},
    ("gurgaon", "3bhk"): {"avg_sqft_price": 13800, "price_low":11000, "price_high": 17000, "monthly_rent_per_sqft": 40, "appreciation_yoy": 7.9, "comparables": 158},
    # Noida
    ("noida", "1bhk"):   {"avg_sqft_price": 6500, "price_low": 5200, "price_high": 8000, "monthly_rent_per_sqft": 18, "appreciation_yoy": 7.8, "comparables": 231},
    ("noida", "2bhk"):   {"avg_sqft_price": 7200, "price_low": 5800, "price_high": 8800, "monthly_rent_per_sqft": 20, "appreciation_yoy": 8.1, "comparables": 412},
    ("noida", "3bhk"):   {"avg_sqft_price": 8000, "price_low": 6500, "price_high": 9800, "monthly_rent_per_sqft": 23, "appreciation_yoy": 7.5, "comparables": 176},
    # Ahmedabad
    ("ahmedabad", "2bhk"): {"avg_sqft_price": 5200, "price_low": 4200, "price_high": 6500, "monthly_rent_per_sqft": 15, "appreciation_yoy": 8.5, "comparables": 298},
    ("ahmedabad", "3bhk"): {"avg_sqft_price": 5800, "price_low": 4700, "price_high": 7200, "monthly_rent_per_sqft": 17, "appreciation_yoy": 8.2, "comparables": 134},
    # Kolkata
    ("kolkata", "2bhk"): {"avg_sqft_price": 5500, "price_low": 4500, "price_high": 6800, "monthly_rent_per_sqft": 16, "appreciation_yoy": 5.8, "comparables": 267},
    ("kolkata", "3bhk"): {"avg_sqft_price": 6200, "price_low": 5000, "price_high": 7600, "monthly_rent_per_sqft": 18, "appreciation_yoy": 5.5, "comparables": 112},
    # Jaipur
    ("jaipur", "2bhk"): {"avg_sqft_price": 4800, "price_low": 3900, "price_high": 6000, "monthly_rent_per_sqft": 13, "appreciation_yoy": 9.2, "comparables": 189},
    # Kochi
    ("kochi", "2bhk"):  {"avg_sqft_price": 6200, "price_low": 5100, "price_high": 7500, "monthly_rent_per_sqft": 19, "appreciation_yoy": 7.1, "comparables": 143},
    # Indore
    ("indore", "2bhk"): {"avg_sqft_price": 4500, "price_low": 3700, "price_high": 5600, "monthly_rent_per_sqft": 13, "appreciation_yoy": 10.1, "comparables": 156},
}

_DEFAULT_MARKET = {"avg_sqft_price": 6500, "price_low": 5000, "price_high": 8500,
                   "monthly_rent_per_sqft": 19, "appreciation_yoy": 7.5, "comparables": 120}


def _resolve_city(city: str) -> str:
    return _CITY_ALIASES.get(city.strip().lower(), city.strip().lower())


def _resolve_bhk(bhk_type: str) -> str:
    normalized = bhk_type.strip().lower().replace(" ", "").replace("-", "")
    for key in ("1bhk", "2bhk", "3bhk", "4bhk"):
        if key in normalized:
            return key
    if "studio" in normalized:
        return "1bhk"
    return "2bhk"  # sensible default


# ── Banker tool implementations ────────────────────────────────────────────────

def calculate_emi(
    principal: float,
    annual_interest_rate: float,
    tenure_years: int,
) -> Dict[str, Any]:
    """
    Compute home-loan EMI using the standard reducing-balance formula.

    Parameters
    ----------
    principal           : Loan amount in ₹
    annual_interest_rate: Interest rate in % per annum (e.g. 8.5 for 8.5%)
    tenure_years        : Loan tenure in years

    Returns
    -------
    dict with monthly_emi, total_payment, total_interest, effective_rate_monthly,
    affordability_band (comfortable / stretched / over-leveraged based on EMI/income heuristics).
    """
    if principal <= 0 or annual_interest_rate <= 0 or tenure_years <= 0:
        return {"error": "All parameters must be positive numbers."}

    monthly_rate = annual_interest_rate / 100 / 12
    n = tenure_years * 12
    emi = principal * monthly_rate * (1 + monthly_rate) ** n / ((1 + monthly_rate) ** n - 1)
    total_payment = emi * n
    total_interest = total_payment - principal

    # Rough affordability heuristic: EMI/income ratio bands
    # (income is unknown here so we express ratio thresholds)
    emi_to_income_guide = (
        "Comfortable if monthly income ≥ ₹{:.0f} (40% FOIR). "
        "Stretched if income ₹{:.0f}–₹{:.0f} (40–55%). "
        "Over-leveraged if income < ₹{:.0f} (>55% FOIR)."
    ).format(emi / 0.40, emi / 0.55, emi / 0.40, emi / 0.55)

    result = {
        "loan_amount_inr": round(principal),
        "annual_interest_rate_pct": annual_interest_rate,
        "tenure_years": tenure_years,
        "monthly_emi_inr": round(emi, 2),
        "total_payment_inr": round(total_payment, 2),
        "total_interest_inr": round(total_interest, 2),
        "interest_to_principal_ratio": round(total_interest / principal, 3),
        "affordability_guide": emi_to_income_guide,
    }
    logger.info("[TOOL] calculate_emi → EMI=₹%s | Total Interest=₹%s",
                f"{emi:,.0f}", f"{total_interest:,.0f}")
    return result


def assess_loan_eligibility(
    monthly_income: float,
    existing_emi_obligations: float = 0.0,
    annual_interest_rate: float = 8.75,
    tenure_years: int = 20,
    ltv_ratio: float = 80.0,
) -> Dict[str, Any]:
    """
    Determine maximum eligible home loan using FOIR (Fixed Obligations to Income Ratio).

    Parameters
    ----------
    monthly_income            : Gross monthly income in ₹
    existing_emi_obligations  : Sum of all existing EMIs in ₹/month
    annual_interest_rate      : Expected home loan rate % p.a.
    tenure_years              : Proposed loan tenure in years
    ltv_ratio                 : Loan-to-Value ratio the bank offers (default 80%)

    Returns
    -------
    dict with max_eligible_loan, recommended_down_payment, net_take_home_after_emi,
    foir_utilised_pct, and risk_rating.
    """
    if monthly_income <= 0:
        return {"error": "Monthly income must be positive."}

    foir_cap = 0.50  # RBI guideline: max 50% FOIR
    max_affordable_emi = foir_cap * monthly_income - existing_emi_obligations
    if max_affordable_emi <= 0:
        return {
            "error": "Existing EMI obligations already exceed 50% FOIR limit.",
            "existing_emi_obligations_inr": round(existing_emi_obligations),
            "foir_limit_inr": round(foir_cap * monthly_income),
        }

    monthly_rate = annual_interest_rate / 100 / 12
    n = tenure_years * 12
    # Derive max principal from affordable EMI
    max_loan = max_affordable_emi * ((1 + monthly_rate) ** n - 1) / (monthly_rate * (1 + monthly_rate) ** n)

    # LTV cap: property value implies max loan
    max_property_value = max_loan / (ltv_ratio / 100)
    recommended_down_payment = max_property_value * (1 - ltv_ratio / 100)
    foir_used = (existing_emi_obligations + max_affordable_emi) / monthly_income * 100

    risk_rating = "Low" if foir_used <= 40 else ("Medium" if foir_used <= 50 else "High")

    result = {
        "monthly_income_inr": round(monthly_income),
        "existing_obligations_inr": round(existing_emi_obligations),
        "max_affordable_emi_inr": round(max_affordable_emi, 2),
        "max_eligible_loan_inr": round(max_loan),
        "max_property_value_at_ltv_inr": round(max_property_value),
        "recommended_min_down_payment_inr": round(recommended_down_payment),
        "foir_utilised_pct": round(foir_used, 1),
        "ltv_ratio_pct": ltv_ratio,
        "risk_rating": risk_rating,
        "note": (
            f"Based on ₹{monthly_income:,.0f}/mo income with {ltv_ratio}% LTV at "
            f"{annual_interest_rate}% p.a. over {tenure_years} years."
        ),
    }
    logger.info("[TOOL] assess_loan_eligibility → max_loan=₹%s | FOIR=%.1f%% | Risk=%s",
                f"{max_loan:,.0f}", foir_used, risk_rating)
    return result


# ── Broker tool implementations ────────────────────────────────────────────────

def fetch_property_pricing(
    city: str,
    bhk_type: str,
    area_sqft: float = 0.0,
) -> Dict[str, Any]:
    """
    Fetch current market price data for a given city and property type.

    Parameters
    ----------
    city        : Indian city name (e.g. "Pune", "Bangalore", "Mumbai")
    bhk_type    : Property configuration (e.g. "2BHK", "3BHK", "1BHK", "Studio")
    area_sqft   : Carpet area in sqft (optional — used to compute total price estimate)

    Returns
    -------
    dict with avg_price_per_sqft, price_range, estimated_total_price (if area given),
    yoy_appreciation_pct, active_comparables, and market_sentiment.
    """
    city_slug = _resolve_city(city)
    bhk_slug = _resolve_bhk(bhk_type)
    data = _MARKET_DATA.get((city_slug, bhk_slug), _MARKET_DATA.get((city_slug, "2bhk"), _DEFAULT_MARKET))

    avg_price = data["avg_sqft_price"]
    price_low = data["price_low"]
    price_high = data["price_high"]
    appreciation = data["appreciation_yoy"]
    comparables = data["comparables"]

    # Market sentiment from appreciation
    if appreciation >= 10:
        sentiment = "Strong Seller's Market — high demand, limited inventory."
    elif appreciation >= 7:
        sentiment = "Moderate Seller's Market — steady appreciation, good entry point."
    elif appreciation >= 4:
        sentiment = "Balanced Market — negotiation possible, check micro-location."
    else:
        sentiment = "Buyer's Market — slower appreciation, higher negotiation leverage."

    result: Dict[str, Any] = {
        "city": city.title(),
        "bhk_type": bhk_type.upper(),
        "avg_price_per_sqft_inr": avg_price,
        "price_range_per_sqft_inr": f"₹{price_low:,} – ₹{price_high:,}",
        "yoy_appreciation_pct": appreciation,
        "active_comparable_listings": comparables,
        "market_sentiment": sentiment,
        "data_source": "PropTech India Mock Index (Aug 2026)",
    }

    if area_sqft and area_sqft > 0:
        result["estimated_total_price_inr"] = round(avg_price * area_sqft)
        result["estimated_total_price_range_inr"] = (
            f"₹{price_low * area_sqft:,.0f} – ₹{price_high * area_sqft:,.0f}"
        )

    logger.info("[TOOL] fetch_property_pricing → %s %s | ₹%s/sqft | +%.1f%% YoY",
                city.title(), bhk_type.upper(), f"{avg_price:,}", appreciation)
    return result


def estimate_rental_yield(
    city: str,
    bhk_type: str,
    property_price_inr: float,
    area_sqft: float = 0.0,
) -> Dict[str, Any]:
    """
    Estimate rental yield and return metrics for a given property.

    Parameters
    ----------
    city                : Indian city name
    bhk_type            : Property configuration (e.g. "2BHK")
    property_price_inr  : Total purchase price in ₹
    area_sqft           : Carpet area (sqft). If 0, uses a BHK-based size estimate.

    Returns
    -------
    dict with estimated_monthly_rent, gross_rental_yield_pct, net_rental_yield_pct
    (after 20% expenses), annual_rental_income, and payback_years.
    """
    if property_price_inr <= 0:
        return {"error": "Property price must be positive."}

    city_slug = _resolve_city(city)
    bhk_slug = _resolve_bhk(bhk_type)
    data = _MARKET_DATA.get((city_slug, bhk_slug), _MARKET_DATA.get((city_slug, "2bhk"), _DEFAULT_MARKET))

    # Estimate area if not provided
    if not area_sqft or area_sqft <= 0:
        bhk_typical_sizes = {"1bhk": 550, "2bhk": 850, "3bhk": 1200, "4bhk": 1600}
        area_sqft = bhk_typical_sizes.get(bhk_slug, 850)

    monthly_rent = data["monthly_rent_per_sqft"] * area_sqft
    annual_rent = monthly_rent * 12
    gross_yield = annual_rent / property_price_inr * 100
    # Net yield: deduct maintenance + property tax + vacancy ≈ 20%
    net_yield = gross_yield * 0.80
    payback_years = property_price_inr / annual_rent if annual_rent > 0 else 9999

    result = {
        "city": city.title(),
        "bhk_type": bhk_type.upper(),
        "estimated_area_sqft": round(area_sqft),
        "property_price_inr": round(property_price_inr),
        "estimated_monthly_rent_inr": round(monthly_rent),
        "annual_rental_income_inr": round(annual_rent),
        "gross_rental_yield_pct": round(gross_yield, 2),
        "net_rental_yield_pct": round(net_yield, 2),
        "payback_years": round(payback_years, 1),
        "yield_rating": (
            "Excellent (>4%)" if net_yield >= 4
            else "Good (3–4%)" if net_yield >= 3
            else "Average (2–3%)" if net_yield >= 2
            else "Below Average (<2%)"
        ),
        "note": "Net yield deducts estimated 20% for maintenance, property tax, vacancy, and agent fees.",
    }
    logger.info("[TOOL] estimate_rental_yield → %s %s | rent=₹%s/mo | gross=%.2f%% | net=%.2f%%",
                city.title(), bhk_type.upper(), f"{monthly_rent:,.0f}", gross_yield, net_yield)
    return result


# ── Tool executor (single dispatch point) ─────────────────────────────────────

_TOOL_REGISTRY = {
    "calculate_emi": calculate_emi,
    "assess_loan_eligibility": assess_loan_eligibility,
    "fetch_property_pricing": fetch_property_pricing,
    "estimate_rental_yield": estimate_rental_yield,
}


def execute_tool(name: str, arguments: str | Dict[str, Any]) -> str:
    """
    Dispatch a tool call by name.  Returns a JSON string (tool role message content).
    Never raises — on any error it returns a JSON error object so the LLM can handle it.
    """
    fn = _TOOL_REGISTRY.get(name)
    if fn is None:
        error = {"error": f"Unknown tool '{name}'.  Available: {list(_TOOL_REGISTRY)}"}
        logger.warning("[TOOL] Unknown tool called: %s", name)
        return json.dumps(error)

    try:
        args: Dict[str, Any] = json.loads(arguments) if isinstance(arguments, str) else arguments
        result = fn(**args)
        return json.dumps(result, ensure_ascii=False, default=str)
    except TypeError as exc:
        error = {"error": f"Tool '{name}' called with wrong arguments: {exc}"}
        logger.error("[TOOL] TypeError in %s: %s", name, exc)
        return json.dumps(error)
    except Exception as exc:
        error = {"error": f"Tool '{name}' execution failed: {exc}"}
        logger.exception("[TOOL] Unexpected error in %s", name)
        return json.dumps(error)


# ── OpenAI JSON schema definitions ────────────────────────────────────────────

BANKER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculate_emi",
            "description": (
                "Calculate the exact monthly EMI, total interest, and total payment for a home loan "
                "using the standard reducing-balance formula.  Always call this before quoting any "
                "EMI figure to ensure mathematical precision."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "principal": {
                        "type": "number",
                        "description": "Loan amount in Indian Rupees (₹). E.g. 7200000 for ₹72 Lakh.",
                    },
                    "annual_interest_rate": {
                        "type": "number",
                        "description": "Annual interest rate in percent. E.g. 8.5 for 8.5% p.a.",
                    },
                    "tenure_years": {
                        "type": "integer",
                        "description": "Loan repayment tenure in years. E.g. 20.",
                    },
                },
                "required": ["principal", "annual_interest_rate", "tenure_years"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assess_loan_eligibility",
            "description": (
                "Determine the maximum home loan a borrower is eligible for based on income, "
                "existing obligations, and the bank's FOIR (Fixed Obligation to Income Ratio) limit.  "
                "Use this to validate whether the client can actually afford the proposed purchase."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "monthly_income": {
                        "type": "number",
                        "description": "Gross monthly income in ₹. E.g. 150000 for ₹1.5 Lakh/month.",
                    },
                    "existing_emi_obligations": {
                        "type": "number",
                        "description": "Total of all existing EMIs (car, personal loan, etc.) in ₹/month. Default 0.",
                    },
                    "annual_interest_rate": {
                        "type": "number",
                        "description": "Expected home loan rate % p.a. Default 8.75.",
                    },
                    "tenure_years": {
                        "type": "integer",
                        "description": "Proposed loan tenure in years. Default 20.",
                    },
                    "ltv_ratio": {
                        "type": "number",
                        "description": "Loan-to-Value ratio the bank will offer. Default 80.0 (80%).",
                    },
                },
                "required": ["monthly_income"],
            },
        },
    },
]

BROKER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_property_pricing",
            "description": (
                "Fetch current market price data for a city and property type from the PropTech India Index.  "
                "Returns average price per sqft, price range, YoY appreciation, and market sentiment.  "
                "Always call this before making any price claim or market comparison."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Indian city name. E.g. 'Pune', 'Bangalore', 'Mumbai', 'Hyderabad'.",
                    },
                    "bhk_type": {
                        "type": "string",
                        "description": "Property type. E.g. '1BHK', '2BHK', '3BHK', 'Studio'.",
                    },
                    "area_sqft": {
                        "type": "number",
                        "description": "Carpet area in sqft (optional). Enables total price estimation.",
                    },
                },
                "required": ["city", "bhk_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estimate_rental_yield",
            "description": (
                "Estimate monthly rental income, gross yield, and net yield for a given property.  "
                "Use this to validate rental investment assumptions with real city-level rental data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Indian city name. E.g. 'Pune', 'Bangalore'.",
                    },
                    "bhk_type": {
                        "type": "string",
                        "description": "Property type. E.g. '2BHK', '3BHK'.",
                    },
                    "property_price_inr": {
                        "type": "number",
                        "description": "Total property purchase price in ₹. E.g. 9000000 for ₹90 Lakh.",
                    },
                    "area_sqft": {
                        "type": "number",
                        "description": "Carpet area in sqft. If 0 or omitted, a BHK-typical size is used.",
                    },
                },
                "required": ["city", "bhk_type", "property_price_inr"],
            },
        },
    },
]
