"""Банк фраз споттера. Всё на русском.

id фразы == имя wav-файла в sounds/.
Если у фразы задан hard - это версия с матом, пишется в sounds/{id}__hard.wav
и играет вместо обычной, когда в конфиге swearing = true.

ПЕРСПЕКТИВА: каждая фраза - это споттер/инженер, который говорит ПИЛОТУ.
Не "мои шины умерли" (это слова пилота), а "твои шины умерли". Проверяй
новые фразы на это, иначе радио звучит шизофренично.
"""

from dataclasses import dataclass


# Приоритеты. Меньше число - важнее.
P_SPOTTER = 0   # прерывает всё, что играет
P_URGENT = 1    # флаги, бокс, прокол
P_NORMAL = 2    # позиции, отрывы, погода
P_INFO = 3      # фоновая информация


# Симы. Пустой sims у фразы = нужна везде.
SIM_F1 = "f1"
SIM_LMU = "lmu"
SIM_ACC = "acc"
SIM_AMS2 = "ams2"
SIM_IRACING = "iracing"

SIM_TITLES = {
    SIM_F1: "F1 25 / F1 24",
    SIM_LMU: "Le Mans Ultimate",
    SIM_ACC: "Assetto Corsa Competizione",
    SIM_AMS2: "Automobilista 2 / Project CARS 2",
    SIM_IRACING: "iRacing",
}

ALL_SIMS = list(SIM_TITLES.keys())

# Где пригодятся эндуранс-фразы: классы, смена пилота, ночь.
ENDURANCE = (SIM_LMU, SIM_ACC, SIM_IRACING, SIM_AMS2)


@dataclass(frozen=True)
class Phrase:
    id: str
    text: str
    priority: int
    group: str
    core: bool = False   # минимум, без которого споттер бесполезен
    hard: str = ""       # версия с матом (необязательно)
    note: str = ""
    sims: tuple[str, ...] = ()   # пусто = фраза общая для всех симов

    def for_sim(self, sim: str | None) -> bool:
        if sim is None or not self.sims:
            return True
        return sim in self.sims


PHRASES: list[Phrase] = [
    # ==================================================================
    # СПОТТЕР. Коротко, резко. Самое важное - это спасает от аварий.
    # ==================================================================
    Phrase("car_left", "слева", P_SPOTTER, "spotter", core=True,
           note="резко, отрывисто, одно слово"),
    Phrase("car_right", "справа", P_SPOTTER, "spotter", core=True,
           note="резко, отрывисто, одно слово"),
    Phrase("car_left_2", "машина слева", P_SPOTTER, "spotter", core=True,
           note="вариант, чтобы не приедалось"),
    Phrase("car_right_2", "машина справа", P_SPOTTER, "spotter", core=True,
           note="вариант, чтобы не приедалось"),
    Phrase("three_wide", "с двух сторон", P_SPOTTER, "spotter", core=True,
           hard="блядь, с двух сторон", note="тревожно"),
    Phrase("still_there", "всё ещё рядом", P_SPOTTER, "spotter", core=True),
    Phrase("clear", "чисто", P_SPOTTER, "spotter", core=True,
           note="спокойно, с облегчением"),
    Phrase("clear_2", "свободен", P_SPOTTER, "spotter", core=True),
    Phrase("hold_line", "держи траекторию", P_SPOTTER, "spotter"),
    Phrase("watch_him", "следи за ним", P_SPOTTER, "spotter",
           hard="следи за этим долбоёбом"),
    Phrase("contact", "контакт", P_SPOTTER, "spotter",
           hard="какого хуя он творит"),

    # ==================================================================
    # ФЛАГИ
    # ==================================================================
    Phrase("flag_yellow", "жёлтый флаг", P_URGENT, "flags", core=True),
    Phrase("flag_yellow_sector", "жёлтый флаг в твоём секторе", P_URGENT, "flags", core=True),
    Phrase("flag_double_yellow", "двойной жёлтый, сбрось скорость", P_URGENT, "flags",
           hard="двойной жёлтый, тормози нахуй"),
    Phrase("flag_blue", "синий флаг, пропускай", P_URGENT, "flags", core=True),
    Phrase("flag_red", "красный флаг, сессия остановлена", P_URGENT, "flags"),
    Phrase("flag_green", "зелёный флаг, трасса чистая", P_URGENT, "flags", core=True),
    Phrase("flag_chequered", "клетчатый флаг", P_NORMAL, "flags"),
    Phrase("incident_ahead", "авария впереди", P_URGENT, "flags", core=True,
           hard="авария впереди, блядь, аккуратно"),

    # ==================================================================
    # МАШИНА БЕЗОПАСНОСТИ
    # ==================================================================
    Phrase("sc_deployed", "машина безопасности на трассе", P_URGENT, "safety_car", core=True),
    Phrase("sc_ending", "сейфти кар уходит в этом круге", P_URGENT, "safety_car"),
    Phrase("vsc_deployed", "виртуальная машина безопасности", P_URGENT, "safety_car", core=True),
    Phrase("vsc_ending", "виртуальный сейфти кар заканчивается", P_URGENT, "safety_car"),
    Phrase("race_restart", "гонка возобновляется", P_URGENT, "safety_car"),
    Phrase("close_up", "подтягивайся к машине впереди", P_NORMAL, "safety_car"),

    # ==================================================================
    # ПИТ-СТОП
    # ==================================================================
    Phrase("box_this_lap", "бокс, бокс в этом круге", P_URGENT, "pit", core=True),
    Phrase("box_now", "бокс, бокс, бокс", P_URGENT, "pit", core=True),
    Phrase("stay_out", "остаёшься на трассе", P_NORMAL, "pit"),
    Phrase("limiter_on", "лимитер включен", P_NORMAL, "pit", core=True),
    Phrase("limiter_off", "лимитер выключен", P_NORMAL, "pit", core=True),
    Phrase("limiter_reminder", "включи лимитер", P_URGENT, "pit", core=True,
           hard="лимитер включи, блядь", note="настойчиво, это спасает от штрафа"),
    Phrase("pit_exit_clear", "выезд свободен", P_SPOTTER, "pit"),
    Phrase("pit_exit_car", "машина на выезде, аккуратно", P_SPOTTER, "pit"),
    Phrase("pitlane_speeding", "превышение в пит-лейн", P_URGENT, "pit",
           hard="превышение в пит-лейн, ну ты дал"),
    Phrase("pit_window_open", "окно пит-стопа открыто", P_NORMAL, "pit"),

    # ==================================================================
    # ПОГОДА. F1 25 отдаёт прогноз, так что это реально работает.
    # ==================================================================
    Phrase("weather_dry", "трасса сухая", P_NORMAL, "weather", core=True),
    Phrase("weather_rain_starting", "начинается дождь", P_URGENT, "weather", core=True,
           hard="дождь начинается, блядь"),
    Phrase("weather_rain_light", "лёгкий дождь", P_NORMAL, "weather", core=True),
    Phrase("weather_rain_heavy", "сильный дождь", P_URGENT, "weather", core=True,
           hard="ливень стеной, охуеть"),
    Phrase("weather_storm", "гроза, будет тяжело", P_URGENT, "weather"),
    Phrase("weather_rain_stopping", "дождь заканчивается", P_NORMAL, "weather", core=True),
    Phrase("weather_drying", "трасса сохнет", P_NORMAL, "weather", core=True),
    Phrase("weather_no_change", "погода без изменений", P_INFO, "weather"),
    Phrase("rain_expected_in", "дождь ожидается через", P_URGENT, "weather", core=True,
           note="дальше подставится число и слово минут"),
    Phrase("rain_chance", "вероятность дождя", P_NORMAL, "weather", core=True,
           note="дальше число и слово процентов"),
    Phrase("minutes", "минут", P_NORMAL, "weather", core=True),
    Phrase("percent", "процентов", P_NORMAL, "weather", core=True),
    Phrase("consider_inters", "подумай про промежуточные", P_NORMAL, "weather", core=True),
    Phrase("consider_wets", "пора на дождевые", P_URGENT, "weather", core=True),
    Phrase("consider_slicks", "можно переобуваться на слики", P_NORMAL, "weather", core=True),
    Phrase("box_for_inters", "бокс, промежуточные", P_URGENT, "weather", core=True),
    Phrase("box_for_wets", "бокс, дождевые", P_URGENT, "weather", core=True),
    Phrase("box_for_slicks", "бокс, слики", P_URGENT, "weather", core=True),
    Phrase("wrong_tyres", "ты не на той резине", P_URGENT, "weather",
           hard="ты на хуй не той резине"),

    # ==================================================================
    # ТРАССА
    # ==================================================================
    Phrase("track_temp", "температура трассы", P_INFO, "track", core=True,
           note="дальше число и слово градусов"),
    Phrase("air_temp", "температура воздуха", P_INFO, "track", core=True),
    Phrase("degrees", "градусов", P_INFO, "track", core=True),
    Phrase("track_cold", "трасса холодная, шины будут долго греться", P_NORMAL, "track", core=True),
    Phrase("track_hot", "трасса горячая, береги резину", P_NORMAL, "track", core=True),
    Phrase("track_evolving", "трасса раскатывается, время падает", P_INFO, "track"),
    Phrase("track_wet_line", "по траектории мокро", P_URGENT, "track", core=True),
    Phrase("track_dry_line", "траектория подсохла", P_NORMAL, "track", core=True),
    Phrase("puddles", "лужи на трассе, аккуратно", P_URGENT, "track",
           hard="лужи на трассе, не наеби нам машину"),
    Phrase("low_grip", "сцепления мало", P_NORMAL, "track"),

    # ==================================================================
    # ПРОГРЕВ ШИН И ТОРМОЗОВ
    # ==================================================================
    Phrase("warm_tyres", "грей шины", P_NORMAL, "warmup", core=True),
    Phrase("warm_tyres_2", "прогрей резину как следует", P_NORMAL, "warmup", core=True),
    Phrase("weave", "поработай рулём, грей резину", P_NORMAL, "warmup", core=True),
    Phrase("keep_heat", "держи температуру в шинах", P_NORMAL, "warmup", core=True),
    Phrase("tyres_cold", "шины холодные", P_NORMAL, "warmup", core=True),
    Phrase("tyres_ready", "шины в рабочей температуре", P_NORMAL, "warmup", core=True),
    Phrase("brakes_cold", "тормоза холодные", P_NORMAL, "warmup", core=True),
    Phrase("brakes_ready", "тормоза в рабочей температуре", P_INFO, "warmup"),
    Phrase("brakes_hot", "тормоза перегреваются", P_NORMAL, "warmup", core=True),
    Phrase("out_lap_push", "выездной круг, разогревайся", P_INFO, "warmup"),

    # ==================================================================
    # ШИНЫ
    # ==================================================================
    Phrase("tyres_overheating", "шины перегреваются", P_NORMAL, "tyres", core=True,
           hard="шины перегреваются нахуй, успокойся"),
    Phrase("tyres_worn", "шины на исходе", P_NORMAL, "tyres", core=True),
    Phrase("tyres_critical", "шины убиты, надо в бокс", P_URGENT, "tyres", core=True,
           hard="шины в хлам, езжай в бокс"),
    Phrase("puncture", "прокол", P_SPOTTER, "tyres", core=True,
           hard="прокол, блядь, в бокс", note="кричи, это авария"),
    Phrase("front_locking", "не блокируй передние", P_NORMAL, "tyres", core=True),
    Phrase("tyre_wear", "износ шин", P_INFO, "tyres", core=True,
           note="дальше число и слово процентов"),
    Phrase("graining", "гранулирование резины", P_NORMAL, "tyres"),

    # ==================================================================
    # ТОПЛИВО
    # ==================================================================
    Phrase("fuel_ok", "по топливу всё хорошо", P_INFO, "fuel", core=True),
    Phrase("fuel_save", "экономь топливо", P_NORMAL, "fuel", core=True),
    Phrase("fuel_critical", "топлива в обрез, сильно экономь", P_URGENT, "fuel", core=True,
           hard="топлива в обрез, блядь, экономь"),
    Phrase("fuel_push", "топлива хватает, можешь атаковать", P_INFO, "fuel", core=True),
    Phrase("fuel_laps_left", "топлива на", P_NORMAL, "fuel", core=True,
           note="дальше число и слово кругов"),
    Phrase("laps_word", "кругов", P_NORMAL, "fuel", core=True),

    # ==================================================================
    # ПОВРЕЖДЕНИЯ
    # ==================================================================
    Phrase("damage_front_wing", "переднее крыло повреждено", P_URGENT, "damage", core=True,
           hard="ты крыло разъебал"),
    Phrase("damage_front_wing_bad", "переднее крыло сильно повреждено, в бокс", P_URGENT, "damage", core=True,
           hard="крыло всмятку, блядь, езжай в бокс"),
    Phrase("damage_floor", "днище повреждено", P_NORMAL, "damage",
           hard="днище нахуй пробито"),
    Phrase("damage_rear_wing", "заднее крыло повреждено", P_URGENT, "damage"),
    Phrase("damage_serious", "серьёзные повреждения", P_URGENT, "damage", core=True,
           hard="машина в хлам, блядь"),
    Phrase("check_car", "проверь машину", P_NORMAL, "damage", core=True),
    Phrase("car_ok", "машина цела, продолжай", P_NORMAL, "damage", core=True),

    # ==================================================================
    # ШТРАФЫ
    # ==================================================================
    Phrase("penalty_5s", "пять секунд штрафа", P_URGENT, "penalties", core=True,
           hard="пять секунд штрафа, блядь"),
    Phrase("penalty_10s", "десять секунд штрафа", P_URGENT, "penalties",
           hard="десять секунд штрафа, ну ты дал"),
    Phrase("penalty_drive_through", "штраф, проезд по пит-лейн", P_URGENT,
           "penalties", core=True,
           hard="штраф, проезд по пит-лейн, блядь"),
    Phrase("penalty_stop_go", "штраф, стоп энд гоу", P_URGENT, "penalties",
           core=True, hard="штраф, стоп энд гоу, пиздец",
           note="самый злой штраф - стоять в боксе"),
    Phrase("penalty_stop_go_10", "стоп энд гоу, десять секунд", P_URGENT,
           "penalties", hard="стоп энд гоу десять секунд, ебать"),
    Phrase("serve_penalty_now", "отбывай штраф в этом круге", P_URGENT,
           "penalties", core=True,
           hard="отбывай штраф сейчас, блядь, не тяни"),
    Phrase("penalty_pending", "на тебе висит штраф", P_URGENT, "penalties",
           core=True, hard="на тебе висит штраф, блядь"),
    Phrase("warning_track_limits", "следи за границами трассы", P_NORMAL,
           "penalties", core=True, hard="съедешь ещё раз - штраф, блядь"),
    Phrase("penalty_served", "штраф отбыт, поехали", P_NORMAL, "penalties",
           core=True, hard="штраф отбыт, погнали нахуй"),
    Phrase("give_position_back", "верни позицию", P_URGENT, "penalties",
           core=True, hard="верни позицию нахуй, а то штраф"),
    Phrase("penalty_speeding", "штраф за превышение в пит-лейн", P_URGENT,
           "penalties", hard="штраф за превышение, ну куда ты гнал"),

    # ==================================================================
    # ПОЗИЦИЯ. Склейка: "ты" + порядковое.
    # ==================================================================
    Phrase("you_are", "ты", P_NORMAL, "position", core=True,
           note="склеивается с числом: ты + третий"),
    Phrase("ord_1", "первый", P_NORMAL, "position", core=True),
    Phrase("ord_2", "второй", P_NORMAL, "position", core=True),
    Phrase("ord_3", "третий", P_NORMAL, "position", core=True),
    Phrase("ord_4", "четвёртый", P_NORMAL, "position", core=True),
    Phrase("ord_5", "пятый", P_NORMAL, "position", core=True),
    Phrase("ord_6", "шестой", P_NORMAL, "position", core=True),
    Phrase("ord_7", "седьмой", P_NORMAL, "position", core=True),
    Phrase("ord_8", "восьмой", P_NORMAL, "position", core=True),
    Phrase("ord_9", "девятый", P_NORMAL, "position", core=True),
    Phrase("ord_10", "десятый", P_NORMAL, "position", core=True),
    Phrase("ord_11", "одиннадцатый", P_NORMAL, "position"),
    Phrase("ord_12", "двенадцатый", P_NORMAL, "position"),
    Phrase("ord_13", "тринадцатый", P_NORMAL, "position"),
    Phrase("ord_14", "четырнадцатый", P_NORMAL, "position"),
    Phrase("ord_15", "пятнадцатый", P_NORMAL, "position"),
    Phrase("ord_16", "шестнадцатый", P_NORMAL, "position"),
    Phrase("ord_17", "семнадцатый", P_NORMAL, "position"),
    Phrase("ord_18", "восемнадцатый", P_NORMAL, "position"),
    Phrase("ord_19", "девятнадцатый", P_NORMAL, "position"),
    Phrase("ord_20", "двадцатый", P_NORMAL, "position"),
    Phrase("position_gained", "отличный обгон", P_NORMAL, "position", core=True,
           hard="охуенный обгон"),
    Phrase("position_lost", "тебя обошли", P_NORMAL, "position", core=True,
           hard="тебя обошли, блядь, соберись"),

    # ==================================================================
    # ЧИСЛА. Нужны для отрывов, температур, процентов, кругов.
    # ==================================================================
    Phrase("num_0", "ноль", P_NORMAL, "numbers", core=True),
    Phrase("num_1", "один", P_NORMAL, "numbers", core=True),
    Phrase("num_2", "два", P_NORMAL, "numbers", core=True),
    Phrase("num_3", "три", P_NORMAL, "numbers", core=True),
    Phrase("num_4", "четыре", P_NORMAL, "numbers", core=True),
    Phrase("num_5", "пять", P_NORMAL, "numbers", core=True),
    Phrase("num_6", "шесть", P_NORMAL, "numbers", core=True),
    Phrase("num_7", "семь", P_NORMAL, "numbers", core=True),
    Phrase("num_8", "восемь", P_NORMAL, "numbers", core=True),
    Phrase("num_9", "девять", P_NORMAL, "numbers", core=True),
    Phrase("num_10", "десять", P_NORMAL, "numbers", core=True),
    Phrase("num_11", "одиннадцать", P_NORMAL, "numbers", core=True),
    Phrase("num_12", "двенадцать", P_NORMAL, "numbers", core=True),
    Phrase("num_13", "тринадцать", P_NORMAL, "numbers", core=True),
    Phrase("num_14", "четырнадцать", P_NORMAL, "numbers", core=True),
    Phrase("num_15", "пятнадцать", P_NORMAL, "numbers", core=True),
    Phrase("num_16", "шестнадцать", P_NORMAL, "numbers", core=True),
    Phrase("num_17", "семнадцать", P_NORMAL, "numbers", core=True),
    Phrase("num_18", "восемнадцать", P_NORMAL, "numbers", core=True),
    Phrase("num_19", "девятнадцать", P_NORMAL, "numbers", core=True),
    Phrase("num_20", "двадцать", P_NORMAL, "numbers", core=True),
    Phrase("num_30", "тридцать", P_NORMAL, "numbers", core=True),
    Phrase("num_40", "сорок", P_NORMAL, "numbers", core=True),
    Phrase("num_50", "пятьдесят", P_NORMAL, "numbers", core=True),
    Phrase("num_60", "шестьдесят", P_NORMAL, "numbers", core=True),
    Phrase("num_70", "семьдесят", P_NORMAL, "numbers", core=True),
    Phrase("num_80", "восемьдесят", P_NORMAL, "numbers", core=True),
    Phrase("num_90", "девяносто", P_NORMAL, "numbers", core=True),
    Phrase("num_100", "сто", P_NORMAL, "numbers", core=True),

    # ==================================================================
    # ОТРЫВЫ
    # ==================================================================
    Phrase("gap_ahead", "до машины впереди", P_NORMAL, "gaps", core=True,
           note="дальше число: до машины впереди + два + и + пять + секунды"),
    Phrase("gap_behind", "преследователь в", P_NORMAL, "gaps", core=True),
    Phrase("gap_leader", "от лидера", P_NORMAL, "gaps", core=True),
    Phrase("seconds", "секунды", P_NORMAL, "gaps", core=True),
    Phrase("point", "и", P_NORMAL, "gaps", core=True,
           note="разделитель целой и десятой: два И пять"),
    Phrase("closing", "ты догоняешь", P_NORMAL, "gaps", core=True),
    Phrase("pulling_away", "он отрывается", P_NORMAL, "gaps", core=True),
    Phrase("in_drs_range", "ты в зоне DRS", P_NORMAL, "gaps", core=True),
    Phrase("he_is_faster", "он быстрее тебя", P_NORMAL, "gaps"),
    Phrase("push_now", "жми, сейчас твой шанс", P_NORMAL, "gaps",
           hard="жми, блядь, давай"),

    # ==================================================================
    # КРУГИ
    # ==================================================================
    Phrase("last_lap", "последний круг", P_URGENT, "laps", core=True),
    Phrase("laps_remaining", "осталось кругов", P_NORMAL, "laps", core=True),
    Phrase("half_distance", "половина дистанции", P_INFO, "laps"),
    Phrase("fastest_lap", "быстрейший круг гонки", P_NORMAL, "laps", core=True,
           hard="быстрейший круг, охуенно"),
    Phrase("personal_best", "личный рекорд", P_NORMAL, "laps", core=True),
    Phrase("good_lap", "хороший круг", P_INFO, "laps", core=True),
    Phrase("lap_invalid", "круг не засчитан", P_NORMAL, "laps", core=True,
           hard="круг не засчитан, блядь"),
    Phrase("purple_sector", "фиолетовый сектор", P_INFO, "laps"),

    # ==================================================================
    # DRS. Только там, где он есть.
    # ==================================================================
    Phrase("drs_enabled", "DRS разрешён", P_NORMAL, "drs", core=True,
           sims=(SIM_F1, SIM_AMS2)),
    Phrase("drs_disabled", "DRS запрещён", P_NORMAL, "drs", core=True,
           sims=(SIM_F1, SIM_AMS2)),
    Phrase("drs_open_it", "открывай DRS", P_NORMAL, "drs",
           sims=(SIM_F1, SIM_AMS2)),

    # ==================================================================
    # ЭНДУРАНС: классы, трафик, смена пилота, ночь.
    # LMU, ACC, iRacing, AMS2.
    # ==================================================================
    Phrase("traffic_ahead", "трафик впереди", P_NORMAL, "endurance", core=True,
           sims=ENDURANCE),
    Phrase("faster_class_behind", "сзади быстрый класс, пропусти", P_URGENT,
           "endurance", core=True, sims=ENDURANCE,
           hard="сзади быстрый класс, съебись с траектории"),
    Phrase("prototype_behind", "прототип сзади", P_URGENT, "endurance",
           core=True, sims=(SIM_LMU, SIM_IRACING, SIM_AMS2)),
    Phrase("prototype_ahead", "прототип впереди", P_NORMAL, "endurance",
           sims=(SIM_LMU, SIM_IRACING, SIM_AMS2)),
    Phrase("gt_ahead", "GT впереди, обгоняй", P_NORMAL, "endurance",
           core=True, sims=ENDURANCE),
    Phrase("gt_behind", "GT сзади", P_INFO, "endurance", sims=ENDURANCE),
    Phrase("let_him_by", "пропусти его", P_URGENT, "endurance", core=True,
           sims=ENDURANCE, hard="пропусти его нахуй"),
    Phrase("lapped_car_ahead", "круговой впереди", P_NORMAL, "endurance",
           core=True, sims=ENDURANCE),
    Phrase("driver_change", "смена пилота на следующем заезде", P_NORMAL,
           "endurance", sims=(SIM_LMU, SIM_ACC, SIM_IRACING)),
    Phrase("stint_ending", "стинт заканчивается", P_NORMAL, "endurance",
           core=True, sims=ENDURANCE),
    Phrase("double_stint", "едешь двойной стинт", P_NORMAL, "endurance",
           sims=ENDURANCE),
    Phrase("headlights_on", "включи фары", P_URGENT, "endurance", core=True,
           sims=ENDURANCE, hard="фары включи, блядь"),
    Phrase("night_falling", "темнеет, скоро фары", P_NORMAL, "endurance",
           core=True, sims=ENDURANCE),
    Phrase("sunrise", "светает", P_INFO, "endurance", sims=ENDURANCE),
    Phrase("fcy", "полная жёлтая по трассе, сбрось скорость", P_URGENT,
           "endurance", core=True, sims=(SIM_LMU, SIM_IRACING, SIM_AMS2),
           note="Full Course Yellow - в эндурансе это важно"),
    Phrase("fcy_end", "жёлтая снята, гонка", P_URGENT, "endurance",
           sims=(SIM_LMU, SIM_IRACING, SIM_AMS2)),
    Phrase("slow_zone", "медленная зона впереди", P_URGENT, "endurance",
           sims=(SIM_LMU,)),
    Phrase("save_the_car", "береги машину, гонка длинная", P_INFO,
           "endurance", core=True, sims=ENDURANCE),

    # ==================================================================
    # iRACING: инциденты.
    # ==================================================================
    Phrase("incident", "инцидент засчитан", P_NORMAL, "iracing", core=True,
           sims=(SIM_IRACING,), hard="инцидент, блядь"),
    Phrase("incident_careful", "аккуратнее, инциденты копятся", P_URGENT,
           "iracing", core=True, sims=(SIM_IRACING,)),
    Phrase("clean_race", "едешь чисто, молодец", P_INFO, "iracing",
           sims=(SIM_IRACING,)),

    # ==================================================================
    # ТРАССЫ. Играет при заходе в сессию: "Ле-Ман. Гонка."
    # Записывай так, как реально называешь их вслух.
    # ==================================================================
    Phrase("welcome_to", "сегодня едем", P_NORMAL, "tracks", core=True,
           note="дальше подставится трасса и тип сессии"),

    # --- календарь LMU (WEC + ELMS): всё, где реально гоняешь в LMU
    Phrase("track_lemans", "Ле-Ман", P_NORMAL, "tracks", core=True,
           sims=(SIM_LMU,)),
    Phrase("track_sebring", "Себринг", P_NORMAL, "tracks", core=True,
           sims=(SIM_LMU,)),
    Phrase("track_fuji", "Фудзи", P_NORMAL, "tracks", core=True,
           sims=(SIM_LMU,)),
    Phrase("track_portimao", "Портимао", P_NORMAL, "tracks", core=True),
    Phrase("track_paul_ricard", "Поль Рикар", P_NORMAL, "tracks", core=True,
           sims=(SIM_LMU,)),
    Phrase("track_mugello", "Муджелло", P_NORMAL, "tracks", core=True,
           sims=(SIM_LMU,)),
    Phrase("track_aragon", "Арагон", P_NORMAL, "tracks", core=True,
           sims=(SIM_LMU,)),
    Phrase("track_nurburgring", "Нюрбургринг", P_NORMAL, "tracks",
           sims=(SIM_ACC, SIM_AMS2, SIM_IRACING)),

    Phrase("track_spa", "Спа", P_NORMAL, "tracks", core=True),
    Phrase("track_monza", "Монца", P_NORMAL, "tracks", core=True),
    Phrase("track_imola", "Имола", P_NORMAL, "tracks", core=True),
    Phrase("track_bahrain", "Бахрейн", P_NORMAL, "tracks", core=True),
    Phrase("track_interlagos", "Интерлагос", P_NORMAL, "tracks", core=True),
    Phrase("track_cota", "Остин", P_NORMAL, "tracks", core=True),
    Phrase("track_qatar", "Катар", P_NORMAL, "tracks", core=True),
    Phrase("track_silverstone", "Сильверстоун", P_NORMAL, "tracks", core=True),
    Phrase("track_barcelona", "Барселона", P_NORMAL, "tracks"),
    # --- этих в LMU нет, не предлагаем их там
    Phrase("track_suzuka", "Судзука", P_NORMAL, "tracks", core=True,
           sims=(SIM_F1, SIM_ACC, SIM_AMS2, SIM_IRACING)),
    Phrase("track_zandvoort", "Зандворт", P_NORMAL, "tracks",
           sims=(SIM_F1, SIM_ACC, SIM_AMS2, SIM_IRACING)),
    Phrase("track_hungaroring", "Хунгароринг", P_NORMAL, "tracks",
           sims=(SIM_F1, SIM_ACC, SIM_AMS2, SIM_IRACING)),
    Phrase("track_red_bull_ring", "Ред Булл Ринг", P_NORMAL, "tracks",
           sims=(SIM_F1, SIM_ACC, SIM_AMS2, SIM_IRACING)),

    Phrase("track_monaco", "Монако", P_NORMAL, "tracks", core=True,
           sims=(SIM_F1,)),
    Phrase("track_melbourne", "Мельбурн", P_NORMAL, "tracks", sims=(SIM_F1,)),
    Phrase("track_shanghai", "Шанхай", P_NORMAL, "tracks", sims=(SIM_F1,)),
    Phrase("track_montreal", "Монреаль", P_NORMAL, "tracks", sims=(SIM_F1,)),
    Phrase("track_baku", "Баку", P_NORMAL, "tracks", sims=(SIM_F1,)),
    Phrase("track_singapore", "Сингапур", P_NORMAL, "tracks", sims=(SIM_F1,)),
    Phrase("track_mexico", "Мехико", P_NORMAL, "tracks", sims=(SIM_F1,)),
    Phrase("track_abu_dhabi", "Абу-Даби", P_NORMAL, "tracks", sims=(SIM_F1,)),
    Phrase("track_jeddah", "Джидда", P_NORMAL, "tracks", sims=(SIM_F1,)),
    Phrase("track_miami", "Майами", P_NORMAL, "tracks", sims=(SIM_F1,)),
    Phrase("track_vegas", "Лас-Вегас", P_NORMAL, "tracks", sims=(SIM_F1,)),
    Phrase("track_unknown", "трасса", P_NORMAL, "tracks", core=True,
           note="запасной вариант, если трассу не узнали"),

    # ==================================================================
    # ТИП СЕССИИ
    # ==================================================================
    Phrase("session_practice", "свободная практика", P_NORMAL, "session",
           core=True),
    Phrase("session_qualifying", "квалификация", P_NORMAL, "session",
           core=True),
    Phrase("session_race", "гонка", P_NORMAL, "session", core=True),
    Phrase("session_warmup", "прогревочная сессия", P_NORMAL, "session"),
    Phrase("session_testday", "тестовый день", P_NORMAL, "session"),
    Phrase("session_hotlap", "квалификационный круг", P_NORMAL, "session",
           sims=(SIM_F1,)),
    Phrase("good_luck", "поехали, удачи", P_NORMAL, "session", core=True,
           hard="поехали, ебошь"),
    Phrase("quali_push", "квалификация, один круг - выложись", P_NORMAL,
           "session", core=True),
    Phrase("practice_relax", "практика, никуда не спеши", P_NORMAL, "session"),

    # ==================================================================
    # КЛАССЫ МАШИН (эндуранс)
    # ==================================================================
    Phrase("class_hypercar", "гиперкар", P_NORMAL, "classes", core=True,
           sims=(SIM_LMU, SIM_IRACING)),
    Phrase("class_lmp2", "эл эм пэ два", P_NORMAL, "classes", core=True,
           sims=(SIM_LMU, SIM_IRACING, SIM_AMS2)),
    Phrase("class_lmp3", "эл эм пэ три", P_NORMAL, "classes",
           sims=(SIM_LMU, SIM_IRACING)),
    Phrase("class_gte", "джи ти и", P_NORMAL, "classes",
           sims=(SIM_LMU, SIM_IRACING)),
    Phrase("class_gt3", "джи ти три", P_NORMAL, "classes", core=True,
           sims=ENDURANCE),
    Phrase("hypercar_behind", "гиперкар сзади, пропусти", P_URGENT,
           "classes", core=True, sims=(SIM_LMU, SIM_IRACING),
           hard="гиперкар сзади, съебись"),
    Phrase("hypercar_ahead", "гиперкар впереди", P_NORMAL, "classes",
           sims=(SIM_LMU, SIM_IRACING)),
    Phrase("lmp2_behind", "эл эм пэ два сзади", P_URGENT, "classes",
           core=True, sims=(SIM_LMU, SIM_IRACING, SIM_AMS2)),
    Phrase("gt3_ahead", "джи ти три впереди, обгоняй", P_NORMAL, "classes",
           core=True, sims=ENDURANCE),
    Phrase("gt3_behind", "джи ти три сзади, держи траекторию", P_INFO,
           "classes", sims=ENDURANCE),
    Phrase("class_battle", "борьба в твоём классе", P_NORMAL, "classes",
           core=True, sims=ENDURANCE),
    Phrase("class_leader", "ты лидер класса", P_NORMAL, "classes",
           core=True, sims=ENDURANCE, hard="ты лидер класса, красава"),

    # ==================================================================
    # МЕМЫ. Играют вместо обычных фраз, изредка. Галка "Мемы" в окне.
    # Записывай с душой, это половина удовольствия.
    # ==================================================================
    Phrase("meme_verstappen", "тутутуту, Макс Ферстаппен", P_NORMAL, "memes",
           core=True, hard="тутутуту, блядь, Макс Ферстаппен ебаный",
           note="после обгона, тянуче, как из трансляции"),
    Phrase("meme_schumacher", "ты просто Шумахер", P_NORMAL, "memes",
           core=True, hard="ебать ты Шумахер ебаный",
           note="на быстрейший круг, с восторгом"),
    Phrase("meme_kimi", "понял, не мешаю, ты знаешь что делаешь", P_NORMAL,
           "memes", core=True, hard="да похуй, делай что хочешь",
           note="устало, как инженер, которому Кими сказал отстать"),
    Phrase("meme_bono", "твои шины умерли, Льюис", P_NORMAL, "memes",
           core=True, hard="шины твои сдохли нахуй, Льюис",
           note="сочувственно, как Боно Хэмилтону"),
    Phrase("meme_gp2", "мотор звучит как джи пэ два", P_NORMAL, "memes",
           core=True, hard="мотор у тебя как у ебаной джи пэ два",
           note="виновато, как инженер Алонсо"),
    Phrase("meme_get_in_there", "давай, залетай туда", P_NORMAL, "memes",
           core=True, hard="давай, блядь, залетай нахуй",
           note="орать, как инженер Хэмилтона"),
    Phrase("meme_boat", "ты плывёшь, как на лодке", P_NORMAL, "memes",
           core=True, hard="ты плывёшь нахуй, как на лодке",
           note="когда трасса мокрая"),
    Phrase("meme_champion", "чемпион мира", P_NORMAL, "memes",
           core=True, hard="чемпион мира, блядь, ебать ты дал",
           note="на победу, орать"),
    Phrase("meme_deer", "куда ты лезешь, олень", P_NORMAL, "memes",
           core=True, hard="куда ты лезешь, долбоёб",
           note="когда тебя подрезали"),
    Phrase("meme_valenok", "ну ты и валенок", P_NORMAL, "memes",
           core=True, hard="ну ты и валенок ебаный",
           note="на свою ошибку"),
    Phrase("meme_ice_cream", "улыбайся, ты в телевизоре", P_NORMAL, "memes",
           core=True, hard="улыбайся, блядь, ты в телевизоре"),
    Phrase("meme_not_raikkonen", "ты не Райкконен, успокойся", P_NORMAL,
           "memes", core=True, hard="ты не Райкконен нахуй, успокойся",
           note="когда крутишься"),
    Phrase("meme_smooth", "красиво, плавный оператор", P_NORMAL, "memes",
           core=True, hard="красиво, блядь, плавный оператор",
           note="на чистый круг, как про Сайнса"),
    Phrase("meme_pedal", "педаль в пол и не думай", P_NORMAL, "memes",
           core=True, hard="педаль в пол нахуй, не думай"),
    Phrase("meme_easy", "изи катка", P_NORMAL, "memes", core=True,
           hard="изи катка, блядь"),
    Phrase("meme_dno", "это дно, ты пробил дно", P_NORMAL, "memes",
           core=True, hard="это пиздец, ты пробил дно",
           note="когда всё плохо"),
    Phrase("meme_box_meme", "бокс бокс бокс, я сказал", P_NORMAL, "memes",
           core=True, hard="бокс бокс бокс, блядь, я сказал"),

    # ==================================================================
    # ОБЩЕЕ
    # ==================================================================
    Phrase("radio_check", "связь есть, слышу тебя хорошо", P_NORMAL, "general",
           core=True,
           note="первое, что слышишь при подключении - проверка связи"),
    Phrase("green_green_green", "зелёный, зелёный, зелёный", P_URGENT, "general", core=True,
           note="старт гонки, энергично"),
    Phrase("good_race", "отличная гонка, поздравляю", P_INFO, "general", core=True),
    Phrase("session_end", "сессия завершена", P_INFO, "general", core=True),
    Phrase("focus", "соберись", P_NORMAL, "general", core=True,
           hard="соберись, блядь"),
    Phrase("calm_down", "спокойно, дыши", P_NORMAL, "general"),
    Phrase("nice_one", "красиво", P_INFO, "general",
           hard="красава, блядь"),
]


BY_ID: dict[str, Phrase] = {p.id: p for p in PHRASES}


# Какую фразу мем может собой заменить. Срабатывает изредка (шанс в
# настройках) - мем, который слышишь каждый круг, перестаёт быть мемом.
MEME_FOR: dict[str, tuple[str, ...]] = {
    "position_gained": ("meme_verstappen", "meme_get_in_there", "meme_easy"),
    "position_lost": ("meme_deer",),
    "fastest_lap": ("meme_schumacher", "meme_champion"),
    "personal_best": ("meme_smooth", "meme_schumacher"),
    "good_lap": ("meme_smooth",),
    "lap_invalid": ("meme_valenok", "meme_not_raikkonen"),
    "tyres_critical": ("meme_bono",),
    "tyres_worn": ("meme_bono",),
    "damage_serious": ("meme_gp2", "meme_dno"),
    "damage_front_wing_bad": ("meme_gp2",),
    "track_wet_line": ("meme_boat",),
    "weather_rain_heavy": ("meme_boat",),
    "push_now": ("meme_pedal", "meme_get_in_there"),
    "focus": ("meme_not_raikkonen", "meme_kimi"),
    "warning_track_limits": ("meme_valenok",),
    "box_this_lap": ("meme_box_meme",),
    "good_race": ("meme_champion",),
    "nice_one": ("meme_verstappen", "meme_easy"),
    "still_there": ("meme_kimi",),
    "contact": ("meme_deer",),
    "session_end": ("meme_ice_cream",),
    "fuel_critical": ("meme_dno",),
}

GROUP_TITLES = {
    "spotter": "СПОТТЕР (машина рядом)",
    "flags": "ФЛАГИ",
    "safety_car": "МАШИНА БЕЗОПАСНОСТИ",
    "pit": "ПИТ-СТОП",
    "weather": "ПОГОДА",
    "track": "ТРАССА",
    "warmup": "ПРОГРЕВ ШИН И ТОРМОЗОВ",
    "tyres": "ШИНЫ",
    "fuel": "ТОПЛИВО",
    "damage": "ПОВРЕЖДЕНИЯ",
    "penalties": "ШТРАФЫ",
    "position": "ПОЗИЦИЯ",
    "numbers": "ЧИСЛА",
    "gaps": "ОТРЫВЫ",
    "laps": "КРУГИ",
    "drs": "DRS",
    "tracks": "ТРАССЫ",
    "session": "ТИП СЕССИИ",
    "classes": "КЛАССЫ МАШИН",
    "endurance": "ЭНДУРАНС (классы, трафик, ночь)",
    "iracing": "iRACING (инциденты)",
    "memes": "МЕМЫ",
    "general": "ОБЩЕЕ",
}

GROUP_ORDER = list(GROUP_TITLES.keys())


def grouped(core_only: bool = False,
            sim: str | None = None) -> dict[str, list[Phrase]]:
    """Фразы по группам, в порядке записи. sim=None - вообще все."""
    out: dict[str, list[Phrase]] = {}
    for g in GROUP_ORDER:
        items = [p for p in PHRASES
                 if p.group == g
                 and (p.core or not core_only)
                 and p.for_sim(sim)]
        if items:
            out[g] = items
    return out


def recording_plan(core_only: bool = False, swearing: bool = True,
                   sim: str | None = None) -> list[tuple[str, str, Phrase]]:
    """Плоский список того, что надо записать: (имя файла, текст, фраза)."""
    plan = []
    for items in grouped(core_only, sim).values():
        for p in items:
            plan.append((p.id, p.text, p))
            if swearing and p.hard:
                plan.append((f"{p.id}__hard", p.hard, p))
    return plan


def sim_extra_count(sim: str) -> int:
    """Сколько фраз в банке существуют только ради этого сима."""
    return sum(1 for p in PHRASES if p.sims and sim in p.sims)
