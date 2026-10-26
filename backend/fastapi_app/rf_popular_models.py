"""Марки/модели, которые реально берут в РФ с Кореи и Китая."""
from __future__ import annotations

import re
from typing import Any, Mapping, Optional

# Марка → допустимые модели (латиница, нижний регистр). Короткий код (k5, j7)
# ищем по границе слова, чтобы не зацепить случайные совпадения.
_RF_POPULAR: dict[str, tuple[str, ...]] = {
    "hyundai": (
        "sonata",
        "elantra",
        "avante",
        "tucson",
        "santa fe",
        "santafe",
        "palisade",
        "grandeur",
        "staria",
        "kona",
        "creta",
        "santa cruz",
        "i30",
        "venue",
    ),
    "kia": (
        "k5",
        "k3",
        "k8",
        "k7",
        "optima",
        "sportage",
        "sorento",
        "carnival",
        "seltos",
        "cerato",
        "forte",
        "rio",
        "mohave",
        "telluride",
        "stinger",
        "soul",
        "cadenza",
        "niro",
        "proceed",
    ),
    "genesis": ("g70", "g80", "g90", "gv70", "gv80", "gv60"),
    "ssangyong": ("torres", "rexton", "korando", "tivoli", "musso"),
    "kg mobility": ("torres", "rexton", "korando", "tivoli", "musso"),
    "chevrolet": (
        "trailblazer",
        "trax",
        "equinox",
        "malibu",
        "traverse",
        "tahoe",
        "cruze",
        "captiva",
        "colorado",
    ),
    "renault": ("qm6", "xm3", "koleos", "arkana", "duster", "samsung"),
    "samsung": ("qm6", "xm3"),
    "toyota": (
        "camry",
        "rav4",
        "highlander",
        "land cruiser",
        "prado",
        "corolla",
        "alphard",
        "harrier",
        "sienna",
        "venza",
        "crown",
        "fortuner",
    ),
    "lexus": ("rx", "nx", "es", "lx", "gx", "ux", "is"),
    "honda": ("accord", "cr-v", "crv", "civic", "pilot", "odyssey", "vezel", "hr-v", "hrv"),
    "nissan": ("x-trail", "xtrail", "qashqai", "teana", "pathfinder", "murano", "patrol", "kicks"),
    "mazda": ("cx-5", "cx5", "cx-50", "cx-8", "cx-9", "mazda6", "mazda 6", "6"),
    "volkswagen": ("tiguan", "passat", "teramont", "magotan", "touran", "tayron"),
    "geely": (
        "coolray",
        "atlas",
        "monjaro",
        "preface",
        "okavango",
        "emgrand",
        "boyue",
        "tugella",
        "xingyue",
        "cityray",
    ),
    "haval": ("jolion", "f7", "dargo", "h5", "h6", "h9", "f7x", "m6", "h7"),
    "chery": ("tiggo", "arrizo"),
    "exeed": ("txl", "lx", "rx", "vx", "tx"),
    "changan": (
        "cs55",
        "cs75",
        "cs95",
        "cs35",
        "uni-k",
        "unik",
        "uni-v",
        "univ",
        "uni-t",
        "unit",
        "hunter",
        "lamore",
        "alsvin",
    ),
    "omoda": ("c5", "s5", "c7"),
    "jaecoo": ("j7", "j8", "j5"),
    "tank": ("300", "500", "400", "700"),
    "gac": ("gs8", "gs3", "gs4", "gs5", "m8", "gn8", "emkoo"),
    "gwm": ("poer", "cannon"),
    "mg": ("hs", "zs", "5", "6", "rx5", "gt"),
    "jac": ("js4", "js6", "t6", "t8", "s7"),
    "bestune": ("t77", "t99", "t55"),
    "faw": ("bestune", "t77", "t99"),
    "hongqi": ("h5", "hs5", "h9"),
    "bmw": ("x3", "x5", "x7", "x1", "x6", "3 series", "5 series", "320", "520", "530", "730"),
    "mercedes": ("gle", "glc", "gla", "glb", "gls", "e-class", "s-class", "e200", "e300", "c200", "c300"),
    "audi": ("q5", "q7", "q8", "q3", "a4", "a6", "a8"),
    "volvo": ("xc60", "xc90", "xc40", "s60", "s90"),
    "subaru": ("forester", "outback", "xv", "legacy"),
    "mitsubishi": ("outlander", "pajero", "asx", "eclipse"),
    "ford": ("explorer", "edge", "escape", "mondeo", "kuga", "territory"),
}


def _as_str(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return s


def _norm(s: str) -> str:
    return re.sub(r"[\s_\-]+", " ", s.lower()).strip()


def _model_in_hay(model: str, hay: str) -> bool:
    token = model.strip().lower()
    if not token:
        return False
    compact_hay = hay.replace("-", " ").replace("_", " ")
    compact_model = token.replace("-", " ")
    if token.isdigit() or re.fullmatch(r"[a-z]{1,3}\d{0,2}", token.replace(" ", "").replace("-", "")):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", hay)) or bool(
            re.search(rf"(?<![a-z0-9]){re.escape(compact_model)}(?![a-z0-9])", compact_hay)
        )
    return token in hay or compact_model in compact_hay


def _brand_models(mark: str, hay: str) -> Optional[tuple[str, ...]]:
    nmark = _norm(mark)
    for brand, models in _RF_POPULAR.items():
        if brand in nmark or brand in hay:
            return models
    return None


def is_rf_popular_listing(data: Mapping[str, Any], row: Mapping[str, Any] | None = None) -> bool:
    """True, если марка+модель из списка популярных для параллельного импорта в РФ."""
    blob: dict[str, Any] = {}
    if row:
        blob.update(dict(row))
    blob.update(dict(data))
    mark = _as_str(blob.get("mark") or blob.get("brand") or blob.get("make"))
    model = _as_str(blob.get("model") or blob.get("model_name"))
    generation = _as_str(blob.get("generation"))
    title = _as_str(blob.get("title"))
    hay = _norm(" ".join(x for x in (mark, model, generation, title) if x))
    models = _brand_models(mark, hay)
    if not models:
        return False
    if model and any(_model_in_hay(m, _norm(model) + " " + hay) for m in models):
        return True
    return any(_model_in_hay(m, hay) for m in models)
