"""Базовый класс правила."""

from __future__ import annotations

import time
from typing import Callable, Protocol

from ..state import GameState

Say = Callable[..., None]


class Rule(Protocol):
    def update(self, state: GameState, say: Say) -> None: ...


class Cooldown:
    """Не даёт одной и той же фразе повторяться слишком часто."""

    def __init__(self) -> None:
        self._last: dict[str, float] = {}

    def ready(self, key: str, seconds: float) -> bool:
        now = time.monotonic()
        last = self._last.get(key)
        if last is not None and now - last < seconds:
            return False
        self._last[key] = now
        return True

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._last.clear()
        else:
            self._last.pop(key, None)
