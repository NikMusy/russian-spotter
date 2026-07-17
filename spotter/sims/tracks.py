"""Опознание трассы.

F1 присылает числовой trackId, LMU - строку с названием. Сводим и то и
другое к id фразы из банка.
"""

from __future__ import annotations

# trackId из спецификации F1 (Data Output from F1 25).
F1_TRACKS = {
    0: "track_melbourne",
    1: "track_paul_ricard",
    2: "track_shanghai",
    3: "track_bahrain",
    4: "track_barcelona",
    5: "track_monaco",
    6: "track_montreal",
    7: "track_silverstone",
    9: "track_hungaroring",
    10: "track_spa",
    11: "track_monza",
    12: "track_singapore",
    13: "track_suzuka",
    14: "track_abu_dhabi",
    15: "track_cota",
    16: "track_interlagos",
    17: "track_red_bull_ring",
    19: "track_mexico",
    20: "track_baku",
    21: "track_bahrain",       # короткая
    22: "track_silverstone",   # короткая
    23: "track_cota",          # короткая
    24: "track_suzuka",        # короткая
    26: "track_zandvoort",
    27: "track_imola",
    28: "track_portimao",
    29: "track_jeddah",
    30: "track_miami",
    31: "track_vegas",
    32: "track_qatar",
}

# LMU отдаёт название строкой, поэтому ищем по куску имени.
# Порядок важен: первое совпадение выигрывает.
NAME_MATCH: list[tuple[tuple[str, ...], str]] = [
    (("sarthe", "le mans", "lemans"), "track_lemans"),
    (("sebring",), "track_sebring"),
    (("fuji",), "track_fuji"),
    (("algarve", "portimao", "portimão"), "track_portimao"),
    (("paul ricard", "castellet"), "track_paul_ricard"),
    (("mugello",), "track_mugello"),
    (("aragon", "aragón", "motorland"), "track_aragon"),
    (("nurburgring", "nürburgring", "nordschleife"), "track_nurburgring"),
    (("spa", "francorchamps"), "track_spa"),
    (("monza",), "track_monza"),
    (("imola", "enzo e dino"), "track_imola"),
    (("bahrain", "sakhir"), "track_bahrain"),
    (("interlagos", "carlos pace", "sao paulo", "são paulo"),
     "track_interlagos"),
    (("americas", "cota", "austin"), "track_cota"),
    (("losail", "qatar", "lusail"), "track_qatar"),
    (("silverstone",), "track_silverstone"),
    (("suzuka",), "track_suzuka"),
    (("catalunya", "barcelona"), "track_barcelona"),
    (("zandvoort",), "track_zandvoort"),
    (("hungaroring", "budapest"), "track_hungaroring"),
    (("red bull ring", "spielberg"), "track_red_bull_ring"),
    (("monaco", "monte carlo"), "track_monaco"),
    (("melbourne", "albert park"), "track_melbourne"),
    (("shanghai",), "track_shanghai"),
    (("montreal", "gilles villeneuve"), "track_montreal"),
    (("baku",), "track_baku"),
    (("singapore", "marina bay"), "track_singapore"),
    (("mexico", "hermanos rodriguez"), "track_mexico"),
    (("yas marina", "abu dhabi"), "track_abu_dhabi"),
    (("jeddah",), "track_jeddah"),
    (("miami",), "track_miami"),
    (("vegas",), "track_vegas"),
]

UNKNOWN = "track_unknown"


def by_f1_id(track_id: int) -> str:
    return F1_TRACKS.get(track_id, UNKNOWN)


def by_name(name: str) -> str:
    """Ищем по куску названия: у симов они пишутся по-разному."""
    if not name:
        return UNKNOWN
    low = name.strip().lower()
    for keys, phrase in NAME_MATCH:
        for k in keys:
            if k in low:
                return phrase
    return UNKNOWN
