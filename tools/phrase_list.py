"""Печатает список фраз для записи. Он же пишет sounds/СПИСОК_ФРАЗ.txt."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spotter.audio.phrases import (
    ALL_SIMS, GROUP_TITLES, PHRASES, SIM_TITLES, grouped, recording_plan,
    sim_extra_count,
)

ROOT = Path(__file__).resolve().parents[1]


def build_text() -> str:
    lines = []
    a = lines.append
    a("СПИСОК ФРАЗ ДЛЯ ОЗВУЧКИ")
    a("=" * 70)
    a("")
    a("Записывать через recorder.exe - он сам назовёт файлы правильно.")
    a("")
    a("[!]     core, минимум для рабочего споттера")
    a("(мат)   отдельный дубль той же фразы с матом")
    a("(сим:)  фраза нужна только этим симам, остальным не предлагается")
    a("")

    for g, items in grouped().items():
        a("")
        a(GROUP_TITLES[g])
        a("-" * 70)
        for p in items:
            mark = "[!]" if p.core else "   "
            tail = f"   (сим: {', '.join(p.sims)})" if p.sims else ""
            a(f"{mark} {p.id:<24} {p.text}{tail}")
            if p.note:
                a(f"    {'':<24} ^ {p.note}")
            if p.hard:
                a(f"    {p.id + '__hard':<24} {p.hard}   (мат)")

    a("")
    a("=" * 70)
    a("СКОЛЬКО ЗАПИСЫВАТЬ")
    a("")
    a(f"  {'сим':<34} {'файлов':>7} {'только core':>12}")
    for s in ALL_SIMS:
        a(f"  {SIM_TITLES[s]:<34} {len(recording_plan(sim=s)):>7} "
          f"{len(recording_plan(core_only=True, sim=s)):>12}")
    a("")
    a(f"  {'всё сразу, любой сим':<34} {len(recording_plan()):>7} "
      f"{len(recording_plan(core_only=True)):>12}")
    return "\n".join(lines)


def main() -> None:
    text = build_text()
    out = ROOT / "sounds" / "СПИСОК_ФРАЗ.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")

    hard = sum(1 for p in PHRASES if p.hard)
    core = sum(1 for p in PHRASES if p.core)
    print(f"всего фраз: {len(PHRASES)}   с матом: {hard}   core: {core}")
    print()
    for g, items in grouped().items():
        h = sum(1 for p in items if p.hard)
        extra = f"  (+{h} с матом)" if h else ""
        print(f"  {GROUP_TITLES[g]:<32} {len(items):>3}{extra}")
    print()
    for s in ALL_SIMS:
        print(f"  {SIM_TITLES[s]:<34} {len(recording_plan(sim=s)):>4} файлов"
              f"   своих фраз: {sim_extra_count(s)}")
    print()
    print(f"записал: {out}")


if __name__ == "__main__":
    main()
