"""Unit prices in cents."""

PRICES = {"pen": 150, "cup": 400, "lamp": 1025}


def unit_price(item: str) -> int:
    """Price of one item in cents; unknown items raise KeyError."""
    return PRICES[item]
