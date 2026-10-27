"""Invoice totals."""

from prices import unit_price


def total(lines: list[tuple[str, int]]) -> int:
    """Total in cents for (item, quantity) lines."""
    return sum(unit_price(item) * quantity for item, quantity in lines)


def render(lines: list[tuple[str, int]]) -> str:
    return f"TOTAL {total(lines) / 100:.2f}"
