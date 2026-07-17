"""Русские падежи в числах.

Раньше споттер говорил "один секунды" и "пять секунды" - числа склеивались
без оглядки на род и число. Здесь проверяем, что теперь звучит по-русски.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spotter.audio import numbers
from spotter.audio.phrases import BY_ID

fails = 0


def say(ids):
    """Как это прозвучит вслух."""
    return " ".join(BY_ID[i].text if i in BY_ID else f"<{i}?>" for i in ids)


print("СЕКУНДЫ")
print("-" * 58)
CASES = [
    (1.0, "одна секунда"),
    (2.0, "две секунды"),
    (3.0, "три секунды"),
    (4.0, "четыре секунды"),
    (5.0, "пять секунд"),
    (11.0, "одиннадцать секунд"),
    (12.0, "двенадцать секунд"),
    (14.0, "четырнадцать секунд"),
    (20.0, "двадцать секунд"),
    (21.0, "двадцать одна секунда"),
    (22.0, "двадцать две секунды"),
    (25.0, "двадцать пять секунд"),
]
for value, want in CASES:
    got = say(numbers.with_word(value, "seconds"))
    ok = got == want
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {value:>5.1f} -> {got}")
    if not ok:
        print(f"       ждали: {want}")

print()
print("ДРОБНЫЕ ОТРЫВЫ (как их говорит споттер)")
print("-" * 58)
DEC = [
    (2.4, "две и четыре секунды"),
    (1.5, "одна и пять секунды"),
    (0.8, "ноль и восемь секунды"),
    (5.6, "пять и шесть секунды"),
    (12.3, "двенадцать и три секунды"),
    (3.0, "три секунды"),
]
for value, want in DEC:
    got = say(numbers.with_word(value, "seconds", decimals=True))
    ok = got == want
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {value:>5.1f} -> {got}")
    if not ok:
        print(f"       ждали: {want}")

print()
print("КРУГИ, МИНУТЫ, ПРОЦЕНТЫ, ГРАДУСЫ")
print("-" * 58)
MORE = [
    (1, "laps", "один круг"),
    (2, "laps", "два круга"),
    (5, "laps", "пять кругов"),
    (21, "laps", "двадцать один круг"),
    (1, "minutes", "одна минута"),
    (2, "minutes", "две минуты"),
    (10, "minutes", "десять минут"),
    (15, "minutes", "пятнадцать минут"),
    (1, "percent", "один процент"),
    (3, "percent", "три процента"),
    (70, "percent", "семьдесят процентов"),
    (1, "degrees", "один градус"),
    (22, "degrees", "двадцать два градуса"),
    (30, "degrees", "тридцать градусов"),
    (45, "degrees", "сорок пять градусов"),
]
for value, word, want in MORE:
    got = say(numbers.with_word(value, word))
    ok = got == want
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {value:>3} {word:<8} -> {got}")
    if not ok:
        print(f"       ждали: {want}")

print()
print("ПОЗИЦИИ")
print("-" * 58)
for n, want in ((1, "ты первый"), (3, "ты третий"), (10, "ты десятый")):
    got = "ты " + say(numbers.ordinal(n))
    ok = got == want
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {got}")

print()
print("ИТОГ СЕССИИ")
print("-" * 58)
from spotter.history import Entry
from spotter.rules.result import announce
from spotter.udp.packets import SessionType

for entry, want in [
    (Entry(session_type=SessionType.RACE, grid=8, finish=3, laps=20),
     "финиш, ты приехал третьим а стартовал восьмым отыграл мест пять"),
    (Entry(session_type=SessionType.RACE, grid=2, finish=9, laps=20),
     "финиш, ты приехал девятым а стартовал вторым потерял мест семь"),
    (Entry(session_type=SessionType.RACE, grid=4, finish=4, laps=20),
     "финиш, ты приехал четвёртым а стартовал четвёртым приехал как стартовал"),
    (Entry(session_type=SessionType.Q2, finish=1, laps=5),
     "квалификация закончена, ты отквалился первым"),
    (Entry(session_type=SessionType.P1, finish=6, laps=9),
     "практика закончена"),
]:
    said = []
    announce(entry, lambda *ids, **kw: said.extend(ids))
    got = say(said)
    ok = got == want
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {got}")
    if not ok:
        print(f"       ждали: {want}")

print()
print("ВСЕ ФРАЗЫ СУЩЕСТВУЮТ В БАНКЕ")
print("-" * 58)
need = set()
for v in (1, 2, 3, 5, 11, 21, 22, 45, 70):
    for w in ("seconds", "laps", "minutes", "percent", "degrees"):
        need.update(numbers.with_word(v, w))
    need.update(numbers.with_word(v + 0.4, "seconds", decimals=True))
for n in range(1, 21):
    need.update(numbers.ordinal(n))
    need.add(f"as_{n}")
need.update({"quali_result", "race_result", "started_from", "practice_over",
             "gained_places", "lost_places", "held_position", "wheel_lost"})
missing = sorted(p for p in need if p not in BY_ID)
ok = not missing
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} проверено {len(need)} фраз "
      f"{'| нет в банке: ' + ', '.join(missing) if missing else ''}")

print()
print("-" * 58)
print("ВСЁ ПРОШЛО" if fails == 0 else f"ПРОВАЛОВ: {fails}")
sys.exit(1 if fails else 0)
