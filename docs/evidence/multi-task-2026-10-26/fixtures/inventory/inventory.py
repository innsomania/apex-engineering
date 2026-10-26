"""Summarise an inventory file: one `name,quantity,unit_price` line per item."""

import sys


def load(path: str) -> list[tuple[str, int, float]]:
    items = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                name, quantity, price = line.split(",")
                items.append((name, int(quantity), float(price)))
    return items


def summary(items: list[tuple[str, int, float]]) -> tuple[int, float]:
    """(number of items, total value)."""
    return len(items), round(sum(quantity * price for _, quantity, price in items), 2)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: inventory.py FILE", file=sys.stderr)
        return 2
    count, total = summary(load(argv[0]))
    print(f"{count} items, total {total:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
