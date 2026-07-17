"""Числа -> id фраз, с русскими падежами.

Банк держит числа до двадцати, десятки и сто, поэтому 45 склеивается из
"сорок" + "пять".

Дальше начинается русский язык. "1 секунды" и "5 секунды" - это не по-русски,
а именно так и звучал споттер, пока склонений не было. Правила два:

  * род: секунда женского рода, поэтому "одна" и "две", а не "один" и "два";
  * число: 1 секунда, 2-4 секунды, 5-20 секунд, и всё это повторяется
    каждую сотню, кроме 11-14 - они всегда "секунд".
"""

from __future__ import annotations

_TENS = {20: "num_20", 30: "num_30", 40: "num_40", 50: "num_50",
         60: "num_60", 70: "num_70", 80: "num_80", 90: "num_90"}

ORDINAL_MAX = 20

# Формы существительного: 1 секунда / 2 секунды / 5 секунд.
FORMS = {
    "seconds": ("seconds_1", "seconds_2", "seconds_5"),
    "laps": ("lap_1", "laps_2", "laps_5"),
    "minutes": ("minute_1", "minutes_2", "minutes_5"),
    "percent": ("percent_1", "percent_2", "percent_5"),
    "degrees": ("degree_1", "degrees_2", "degrees_5"),
}

# Числительные женского рода - для секунд и минут.
FEMININE = {1: "num_1f", 2: "num_2f"}


def plural_form(n: int, word: str) -> str:
    """Какую форму слова взять для числа n."""
    one, few, many = FORMS[word]
    n = abs(int(n))
    if 11 <= n % 100 <= 14:
        return many
    last = n % 10
    if last == 1:
        return one
    if 2 <= last <= 4:
        return few
    return many


def integer(n: int, feminine: bool = False) -> list[str]:
    """45 -> [сорок, пять]. Всё, что больше 99, схлопывается в "сто"."""
    n = max(0, int(n))
    if n >= 100:
        return ["num_100"]

    if n <= 20:
        ids = [f"num_{n}"]
        units = n
    else:
        tens, units = (n // 10) * 10, n % 10
        ids = [_TENS[tens]]
        if units:
            ids.append(f"num_{units}")

    # Женский род меняет только последнее слово: "двадцать одна".
    if feminine and units in FEMININE:
        ids[-1] = FEMININE[units]
    return ids


def decimal(value: float, feminine: bool = False) -> list[str]:
    """2.4 -> [две, и, четыре]. Для отрывов."""
    value = abs(value)
    whole = int(value)
    tenth = int(round((value - whole) * 10))
    if tenth >= 10:            # 2.97 округлилось бы в "два и десять"
        whole += 1
        tenth = 0

    # У дробного в женском роде склоняется только целая часть: "две и пять".
    ids = integer(whole, feminine=feminine)
    if tenth > 0:
        ids.extend(("point", f"num_{tenth}"))
    return ids


def with_word(value: float, word: str, decimals: bool = False) -> list[str]:
    """Число вместе с правильной формой слова: 2.4 -> две и четыре секунды.

    У дробных форма всегда как у "2-4": 1.5 секунды, 5.6 секунды.
    """
    feminine = word in ("seconds", "minutes")
    whole = int(abs(value))
    tenth = int(round((abs(value) - whole) * 10))
    if tenth >= 10:
        whole += 1
        tenth = 0

    if decimals and tenth > 0:
        ids = decimal(value, feminine=feminine)
        return ids + [FORMS[word][1]]

    ids = integer(whole, feminine=feminine)
    return ids + [plural_form(whole, word)]


def ordinal(n: int) -> list[str]:
    """Позиция: 3 -> [третий]. Дальше двадцатого банк не тянет."""
    if 1 <= n <= ORDINAL_MAX:
        return [f"ord_{n}"]
    return []
