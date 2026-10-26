"""Customer report helpers."""


def duplicates(names: list[str]) -> list[str]:
    """Names that occur more than once, in order of first appearance, each listed once."""
    result = []
    for name in names:
        if names.count(name) > 1 and name not in result:
            result.append(name)
    return result
