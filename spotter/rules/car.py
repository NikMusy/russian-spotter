"""Правила по машине: лимитер, шины, топливо, повреждения."""

from __future__ import annotations

from ..state import GameState
from ..udp.packets import PitStatus
from .base import Cooldown, Say

# Порог, выше которого в пит-лейн уже штрафуют. Лимитер F1 - 80 км/ч.
PIT_SPEED_MARGIN = 3


class PitLimiterRule:
    """Орёт про лимитер, пока не включил. Это спасает от штрафа."""

    def __init__(self) -> None:
        self.cd = Cooldown()
        # None = ещё не знаем. Иначе первый же кадр выглядит как
        # переключение и споттер зря докладывает про лимитер.
        self.last_limiter: int | None = None
        self.was_in_pits = False

    def update(self, state: GameState, say: Say) -> None:
        me = state.me
        if me is None or state.status is None or state.session is None:
            return

        limiter = state.status.pit_limiter
        in_pits = me.pit_status != PitStatus.NONE

        if self.last_limiter is None:
            self.last_limiter = limiter
        elif limiter != self.last_limiter:
            self.last_limiter = limiter
            # Про лимитер интересно только в пит-лейн. На трассе его
            # дёргают случайно, и доклад про это - лишний шум.
            if in_pits:
                say("limiter_on" if limiter else "limiter_off")

        limit = state.session.pit_speed_limit or 80
        if in_pits and not limiter and state.speed_kmh > limit + PIT_SPEED_MARGIN:
            if self.cd.ready("limiter_warn", 2.5):
                say("limiter_reminder")

        self.was_in_pits = in_pits


# Про холодные шины напоминаем не больше этого раз за стинт. Если трасса
# холодная, резина может вообще не догреться до нормы - и без лимита
# споттер долбил бы одно и то же весь заезд.
MAX_COLD_CALLS = 2
COLD_GAP = 50.0
# Перегрев - вещь временная (пара кругов атаки), но повторять тоже незачем.
MAX_HOT_CALLS = 3
HOT_GAP = 45.0
# Ниже этого - сим просто не отдаёт температуру (нули Кельвина).
NO_DATA_C = -50


class TyreRule:
    def __init__(self) -> None:
        self.cd = Cooldown()
        self.warned_wear: set[int] = set()
        self.last_punctured = False
        self.reported_ready = False
        self.cold_calls = 0
        self.hot_calls = 0
        self.was_in_pits = False

    def update(self, state: GameState, say: Say) -> None:
        # Выехали из пита - новый стинт, шины другие, счётчики обнуляем.
        if self.was_in_pits and not state.in_pits:
            self.on_new_tyres()
        self.was_in_pits = state.in_pits

        if not state.on_track or state.in_pits:
            return

        # Прокол - это авария, говорим сразу.
        if state.damage is not None:
            punctured = any(d >= 80 for d in state.damage.tyre_damage)
            if punctured and not self.last_punctured:
                say("puncture")
            self.last_punctured = punctured

            wear = max(state.damage.tyre_wear)
            for threshold, phrase in ((70, "tyres_worn"), (85, "tyres_critical")):
                if wear >= threshold and threshold not in self.warned_wear:
                    self.warned_wear.add(threshold)
                    say(phrase)

        if state.telemetry is None:
            return
        temps = state.telemetry.tyre_surface_temp
        avg = sum(temps) / len(temps)
        # В боксе и на загрузке сим отдаёт нули Кельвина, из которых
        # получается -273 C. Это "данных нет", а не "шины холодные" -
        # иначе споттер требует греть резину прямо в гараже.
        if avg < NO_DATA_C:
            return

        if avg < 70 and state.speed_kmh > 60:
            if self.cold_calls < MAX_COLD_CALLS and self.cd.ready("cold", COLD_GAP):
                self.cold_calls += 1
                say("warm_tyres")
                self.reported_ready = False
        elif avg > 115:
            if self.hot_calls < MAX_HOT_CALLS and self.cd.ready("hot", HOT_GAP):
                self.hot_calls += 1
                say("tyres_overheating")
        elif 85 <= avg <= 105 and not self.reported_ready:
            if self.cd.ready("ready", 30):
                say("tyres_ready")
                self.reported_ready = True
                # Прогрелись - про холод больше не заикаемся.
                self.cold_calls = MAX_COLD_CALLS

    def on_new_tyres(self) -> None:
        self.warned_wear.clear()
        self.reported_ready = False
        self.cold_calls = 0
        self.hot_calls = 0
        self.cd.reset("cold")
        self.cd.reset("hot")
        self.cd.reset("ready")


class FuelRule:
    def __init__(self) -> None:
        self.cd = Cooldown()
        self.warned: set[str] = set()

    def update(self, state: GameState, say: Say) -> None:
        if state.status is None or not state.in_race or not state.on_track:
            return
        me = state.me
        if me is None or me.current_lap < 2:
            return

        # Запас в кругах относительно остатка гонки.
        delta = state.status.fuel_remaining_laps - state.laps_left

        if delta < -0.6 and "critical" not in self.warned:
            self.warned.add("critical")
            say("fuel_critical")
        elif -0.6 <= delta < -0.15 and "save" not in self.warned:
            self.warned.add("save")
            say("fuel_save")
        elif delta > 1.0 and "push" not in self.warned:
            self.warned.add("push")
            say("fuel_push")


class DamageRule:
    def __init__(self) -> None:
        self.reported: set[str] = set()
        self.lost_wheel = False
        self.rival_wheel = False
        self.was_in_pits = False

    def update(self, state: GameState, say: Say) -> None:
        # В боксе повреждения чинят - после выезда докладываем заново.
        if self.was_in_pits and not state.in_pits:
            self.on_repair()
        self.was_in_pits = state.in_pits

        # Колесо отвалилось - это конец заезда, важнее любых крыльев.
        detached = any(state.wheels_detached)
        if detached and not self.lost_wheel:
            say("wheel_lost")
        self.lost_wheel = detached

        # У машины впереди отвалилось колесо - объезжай обломки.
        if state.rival_lost_wheel_ahead and not self.rival_wheel:
            say("rival_wheel_off")
        self.rival_wheel = state.rival_lost_wheel_ahead

        d = state.damage
        if d is None or not state.on_track:
            return

        wing = max(d.front_left_wing, d.front_right_wing)
        if wing >= 60 and "wing_bad" not in self.reported:
            self.reported.add("wing_bad")
            self.reported.add("wing")
            say("damage_front_wing_bad")
        elif wing >= 20 and "wing" not in self.reported:
            self.reported.add("wing")
            say("damage_front_wing")

        if d.rear_wing >= 30 and "rear" not in self.reported:
            self.reported.add("rear")
            say("damage_rear_wing")

        if d.floor >= 40 and "floor" not in self.reported:
            self.reported.add("floor")
            say("damage_floor")

    def on_repair(self) -> None:
        self.reported.clear()
        self.lost_wheel = False
