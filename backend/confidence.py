from typing import Literal

UNCERTAINTY_MARKERS = [
    "might", "possibly", "depends", "typically", "could", "may",
    "uncertain", "unclear", "generally", "often", "sometimes",
    "potentially", "likely", "probably", "perhaps", "approximately",
    "roughly", "tends to", "can vary", "not sure", "usually",
]


def compute_confidence(text: str) -> Literal["high", "medium", "low"]:
    """Score uncertainty of an agent response by counting hedging markers."""
    t = text.lower()
    count = sum(t.count(m) for m in UNCERTAINTY_MARKERS)
    if count < 2:
        return "high"
    if count <= 5:
        return "medium"
    return "low"
