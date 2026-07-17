"""Проверка, что тесту не мешает настоящая LMU.

CreateFileMapping не создаёт второй объект с именем LMU_Data - он отдаёт
существующий. Поэтому при запущенной игре поддельный симулятор пишет прямо
поверх её данных, и тест видит мешанину из двух источников: погода скачет,
лимитер переключается сам. Это не баг кода, и делать вид, что тест прошёл,
тоже нельзя - поэтому просто выходим с понятным сообщением.
"""

from __future__ import annotations

import sys


def require_no_live_lmu(test_name: str = "") -> None:
    from fake_lmu import FakeLMU, LMUAlreadyRunning

    try:
        probe = FakeLMU()
    except LMUAlreadyRunning:
        print("=" * 62)
        print(f"  ПРОПУСК{': ' + test_name if test_name else ''}")
        print("=" * 62)
        print("  Запущена настоящая Le Mans Ultimate - она держит LMU_Data.")
        print("  Симулятор писал бы поверх её данных, и тест проверял бы")
        print("  мешанину, а не код. Закрой игру и запусти снова.")
        print()
        print("  ПРОПУЩЕНО (не провал)")
        sys.exit(0)
    else:
        probe.close()
