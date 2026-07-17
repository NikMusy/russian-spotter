"""Числа -> id фраз.

Банк держит числа до двадцати, десятки и сто, поэтому 45 склеивается из
"сорок" + "пять". Этого хватает на отрывы, температуры, проценты и круги.
"""

from __future__ import annotations

_TENS = {20: "num_20", 30: "num_30", 40: "num_40", 50: "num_50",
         60: "num_60", 70: "num_70", 80: "num_80", 90: "num_90"}

ORDINAL_MAX = 20


def integer(n: int) -> list[str]:
    """45 -> [сорок, пять]. Всё, что больше 99, схлопывается в "сто"."""
    n = max(0, int(n))
    if n <= 20:
        return [f"num_{n}"]
    if n >= 100:
        return ["num_100"]
    tens, units = (n // 10) * 10, n % 10
    ids = [_TENS[tens]]
    if units:
        ids.append(f"num_{units}")
    return ids


def decimal(value: float) -> list[str]:
    """2.4 -> [два, и, четыре]. Для отрывов."""
    value = abs(value)
    whole = int(value)
    ids = integer(whole)
    tenth = int(round((value - whole) * 10))
    if tenth >= 10:  # 2.97 округлилось бы в "два и десять"
        ids = integer(whole + 1)
        tenth = 0
    if tenth > 0:
        ids.extend(("point", f"num_{tenth}"))
    return ids


def ordinal(n: int) -> list[str]:
    """Позиция: 3 -> [третий]. Дальше двадцатого банк не тянет."""
    if 1 <= n <= ORDINAL_MAX:
        return [f"ord_{n}"]
    return []
