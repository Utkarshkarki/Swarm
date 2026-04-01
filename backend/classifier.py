from typing import List

DOMAIN_KEYWORDS: dict[str, List[str]] = {
    "legal": [
        "title", "deed", "ownership", "zoning", "compliance", "contract",
        "registration", "legal", "rights", "documentation", "rera", "freehold",
        "leasehold", "litigation", "encumbrance", "stamp duty", "power of attorney",
        "dispute", "court", "noc", "occupancy certificate", "nri", "inheritance",
    ],
    "financial": [
        "loan", "mortgage", "emi", "interest rate", "credit", "bank", "afford",
        "financing", "down payment", "home loan", "tax", "gst", "cost", "payment",
        "funds", "liquidity", "debt", "cash flow", "income", "salary", "budget",
    ],
    "investment": [
        "roi", "returns", "yield", "rental income", "appreciation", "profit",
        "investment", "portfolio", "cap rate", "flip", "hold", "exit", "rent",
        "tenant", "landlord", "capital gains", "irr", "passive income",
    ],
    "market": [
        "price", "trend", "market", "locality", "area", "neighborhood",
        "demand", "supply", "comparable", "valuation", "broker", "listing",
        "inventory", "suburb", "location", "city", "district", "sector",
        "township", "micro-market", "appreciation",
    ],
    "construction": [
        "construction", "quality", "builder", "amenities", "defects",
        "renovation", "structural", "completion", "possession", "certificate",
        "floor plan", "bua", "carpet", "super area", "occ", "approval",
        "plan sanction", "developer", "ready to move", "under construction",
    ],
}

DOMAIN_TO_AGENT: dict[str, str] = {
    "market": "broker",
    "investment": "investor",
    "legal": "legal",
    "construction": "developer",
    "financial": "banker",
}


def classify_query(query: str) -> List[str]:
    """Return active domain list. Falls back to all domains if none matched."""
    q = query.lower()
    active = [d for d, kws in DOMAIN_KEYWORDS.items() if any(kw in q for kw in kws)]
    return active if active else list(DOMAIN_KEYWORDS.keys())


def get_active_agent_ids(domains: List[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for d in domains:
        aid = DOMAIN_TO_AGENT.get(d)
        if aid and aid not in seen:
            seen.add(aid)
            result.append(aid)
    return result
