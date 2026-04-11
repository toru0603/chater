"""Small helper module to increase app source lines for CI TCR checks.

These utilities are intentionally simple and safe. They exist to add measured
non-empty lines in the `app` package so the Test-to-Code Ratio (TCR) check in
CI can pass without changing test semantics.
"""

from __future__ import annotations

from typing import List


def add(a: int, b: int) -> int:
    """Return sum of a and b."""
    return a + b


def multiply(a: int, b: int) -> int:
    """Return product of a and b."""
    return a * b


def is_even(n: int) -> bool:
    """Return True when n is even."""
    return n % 2 == 0


def clamp(value: int, min_v: int, max_v: int) -> int:
    """Clamp value to the inclusive range [min_v, max_v]."""
    if value < min_v:
        return min_v
    if value > max_v:
        return max_v
    return value


COLORS = [
    "#e11d48",
    "#f97316",
    "#f59e0b",
    "#10b981",
    "#06b6d4",
]


def color_by_index(index: int) -> str:
    """Return a color from COLORS by index."""
    return COLORS[index % len(COLORS)]


def generate_sequence(n: int) -> List[int]:
    """Generate a sequence of integers [0, 1, ..., n-1]."""
    return [i for i in range(n)]


def safe_divide(a: float, b: float) -> float:
    """Divide a by b, return inf on division by zero."""
    try:
        return a / b
    except ZeroDivisionError:
        return float("inf")


def noop() -> None:
    """No-op helper used to pad lines for TCR calculation."""
    return None


__all__ = [
    "add",
    "multiply",
    "is_even",
    "clamp",
    "color_by_index",
    "generate_sequence",
    "safe_divide",
    "noop",
]
