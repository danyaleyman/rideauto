from __future__ import annotations

import re
from collections import defaultdict
from functools import lru_cache
from typing import Dict, List, Optional, Sequence

from localization.term_localizer import (
    _CHINA_MARK_EXACT_OVERRIDES,
    _KOREA_MARK_ALIAS_OVERRIDES,
    _KOREA_MARK_EXACT_OVERRIDES,
    _as_text,
    _korea_static_maps,
    facet_canonical_english,
    is_china_trim_like_noise,
)

_KO_OR_ZH_RE = re.compile(r"[\uac00-\ud7af\u4e00-\u9fff]")
_JUNK_TRANS_NUMERIC = re.compile(r"^0*\d{1,4}$")

_MEILI_TO_EN_DOMAIN = {
    "brand": "mark",
    "model_group": "model",
    "generation": "generation",
    "trim": "trim_name",
}

_TRANS_EXTRA: Dict[str, str] = {
    "DCT": "Робот (двойное сцепление)",
    "AMT": "Робот",
    "AT": "Автомат",
    "MT": "Механика",
    "cvt": "Вариатор",
}

# Доп. синонимы топлива (уже русские / EN в базе) → канон из korea_static_terms.ru.engine_type
_FUEL_CANON_ALIASES: Dict[str, str] = {
    "Gasoline": "Бензин",
    "gasoline": "Бензин",
    "PETROL": "Бензин",
    "petrol": "Бензин",
    "Diesel": "Дизель",
    "diesel": "Дизель",
    "Electric": "Электричество",
    "electric": "Электричество",
    "EV": "Электричество",
    "Hybrid": "Бензин + электричество",
    "LPG + электричество": "LPG + электричество",
    "LPG+электричество": "LPG + электричество",
}


def is_korea_catalog_flat(q: Optional[Dict[str, str]]) -> bool:
    if not q:
        return False
    src = (q.get("source") or "").strip().lower()
    reg = (q.get("region") or "").strip().lower()
    return reg == "korea" or src == "encar"


def is_china_catalog_flat(q: Optional[Dict[str, str]]) -> bool:
    if not q:
        return False
    src = (q.get("source") or "").strip().lower()
    reg = (q.get("region") or "").strip().lower()
    return reg == "china" or src in {"china", "dongchedi", "che168"}


@lru_cache(maxsize=1)
def _ru_engine_type_map() -> Dict[str, str]:
    m = (_korea_static_maps().get("ru") or {}).get("engine_type") or {}
    return {str(k): str(v) for k, v in m.items() if isinstance(k, str)}


@lru_cache(maxsize=1)
def _ru_body_type_map() -> Dict[str, str]:
    m = (_korea_static_maps().get("ru") or {}).get("body_type") or {}
    return {str(k): str(v) for k, v in m.items() if isinstance(k, str)}


@lru_cache(maxsize=1)
def _ru_color_map() -> Dict[str, str]:
    m = (_korea_static_maps().get("ru") or {}).get("color") or {}
    return {str(k): str(v) for k, v in m.items() if isinstance(k, str)}


@lru_cache(maxsize=1)
def _ru_transmission_map() -> Dict[str, str]:
    m = (_korea_static_maps().get("ru") or {}).get("transmission_type") or {}
    out = {str(k): str(v) for k, v in m.items() if isinstance(k, str)}
    out.update(_TRANS_EXTRA)
    return out


def _invert_map_forward(forward: Dict[str, str]) -> Dict[str, frozenset[str]]:
    inv: Dict[str, set[str]] = defaultdict(set)
    for raw, canon in forward.items():
        r = _as_text(raw)
        c = _as_text(canon)
        if not c:
            continue
        inv[c].add(r)
        inv[c].add(c)
    return {k: frozenset(v) for k, v in inv.items()}


@lru_cache(maxsize=1)
def _fuel_synonyms_by_canon() -> Dict[str, frozenset[str]]:
    forward = dict(_ru_engine_type_map())
    for alias, canon in _FUEL_CANON_ALIASES.items():
        forward[alias] = canon
    inv = _invert_map_forward(forward)
    return inv


@lru_cache(maxsize=1)
def _body_synonyms_by_canon() -> Dict[str, frozenset[str]]:
    return _invert_map_forward(_ru_body_type_map())


@lru_cache(maxsize=1)
def _color_synonyms_by_canon() -> Dict[str, frozenset[str]]:
    return _invert_map_forward(_ru_color_map())


@lru_cache(maxsize=1)
def _trans_synonyms_by_canon() -> Dict[str, frozenset[str]]:
    inv = {k: set(v) for k, v in _invert_map_forward(_ru_transmission_map()).items()}
    inv.setdefault("Вариатор", set()).update(["CVT", "cvt"])
    return {k: frozenset(v) for k, v in inv.items()}


@lru_cache(maxsize=1)
def _brand_synonyms_by_canon() -> Dict[str, frozenset[str]]:
    inv: Dict[str, set[str]] = defaultdict(set)
    for ko, en in ((_korea_static_maps().get("en") or {}).get("mark") or {}).items():
        eng = _as_text(en)
        o = _as_text(ko)
        if not eng:
            continue
        inv[eng].add(eng)
        if o:
            inv[eng].add(o)
    for alias, eng in _KOREA_MARK_ALIAS_OVERRIDES.items():
        if eng:
            inv[eng].add(alias)
            inv[eng].add(eng)
    for hangul, eng in _KOREA_MARK_EXACT_OVERRIDES.items():
        if eng:
            inv[eng].add(hangul)
            inv[eng].add(eng)
    for zh, eng in _CHINA_MARK_EXACT_OVERRIDES.items():
        if eng:
            inv[eng].add(zh)
    return {k: frozenset(v) for k, v in inv.items()}


@lru_cache(maxsize=1)
def _invert_en_domain(domain: str) -> Dict[str, frozenset[str]]:
    inv: Dict[str, set[str]] = defaultdict(set)
    for maps in (_korea_static_maps(),):
        bucket = ((maps.get("en") or {}).get(domain) or {})
        for orig, eng in bucket.items():
            e = _as_text(eng)
            o = _as_text(orig)
            if not e:
                continue
            inv[e].add(e)
            if o:
                inv[e].add(o)
    from localization.term_localizer import _china_static_maps  # lazy import

    bucket_cn = ((_china_static_maps().get("en") or {}).get(domain) or {})
    for orig, eng in bucket_cn.items():
        e = _as_text(eng)
        o = _as_text(orig)
        if not e:
            continue
        inv[e].add(e)
        if o:
            inv[e].add(o)
    return {k: frozenset(v) for k, v in inv.items()}


_CHINA_SUFFIX_MARKERS = (
    " kuan ",
    " ban ",
    " biao ",
    " zhun ",
    " xu hang ",
    " hou qu ",
    " qian qu ",
    " si qu ",
    " zeng cheng ",
    " sheng ji ",
)

_CHINA_SUBSTRING_LABEL_OVERRIDES: Dict[str, str] = {
    "fa xian yun dong": "Discovery Sport",
    "ying lang": "Excelle GT",
    "mao xian jia": "Corsair",
    "凯迪拉克xts": "Cadillac XTS",
    "奕炫gs": "Yixuan GS",
}

_CHINA_PINYIN_TOKEN_REPLACEMENTS: Dict[str, str] = {
    r"\bliang qu\b": "2WD",
    r"\bsi qu\b": "4WD",
    r"\bqian qu\b": "FWD",
    r"\bhou qu\b": "RWD",
    r"\bzeng cheng\b": "EREV",
    r"\bchao chang xu hang\b": "Long Range",
    r"\bchang xu hang\b": "Long Range",
    r"\bbiao zhun\b": "Standard",
    r"\bzhi tu\b": "Zhitu",
    r"\bzhi xiang\b": "Zhixiang",
    r"\bzhi zun\b": "Premium",
    r"\bhao hua\b": "Luxury",
    r"\bqi jian\b": "Flagship",
    r"\bsheng ji\b": "Upgrade",
    r"\bjin kou\b": "Import",
}


def _cleanup_china_facet_value(raw: str, meili_attr: str) -> str:
    s = _as_text(raw)
    if not s:
        return ""
    s = facet_canonical_english(s, _MEILI_TO_EN_DOMAIN.get(meili_attr, ""))
    if not s:
        return ""
    low0 = s.lower()
    for needle, repl in _CHINA_SUBSTRING_LABEL_OVERRIDES.items():
        if needle in low0:
            s = re.sub(re.escape(needle), repl, s, flags=re.IGNORECASE)
            low0 = s.lower()
    for patt, repl in _CHINA_PINYIN_TOKEN_REPLACEMENTS.items():
        s = re.sub(patt, repl, s, flags=re.IGNORECASE)
    s = re.sub(r"[()\[\]{}]+", " ", s)
    if meili_attr in {"model_group", "generation", "trim"}:
        s = re.sub(r"^\d+\s+", "", s).strip()
    s = " ".join(s.split())
    if _KO_OR_ZH_RE.search(s):
        # Для China-фасетов стараемся не показывать иероглифы в UI.
        try:
            from localization.term_localizer import _romanize_zh  # lazy import

            s = " ".join(str(_romanize_zh(s)).split())
        except Exception:
            pass
        if _KO_OR_ZH_RE.search(s):
            s = " ".join(re.sub(r"[\u4e00-\u9fff\uac00-\ud7af]+", " ", s).split())
    # Для model_group гасим «длинные хвосты» комплектации.
    # Для generation/trim наоборот сохраняем максимум смысла (только EN-cleanup).
    if meili_attr == "model_group":
        low = f" {s.lower()} "
        cut = None
        for marker in _CHINA_SUFFIX_MARKERS:
            idx = low.find(marker)
            if idx > 0:
                cut = idx if cut is None else min(cut, idx)
        if cut is not None:
            s = s[:cut].strip()
        m = re.search(r"\b20\d{2}\b", s)
        if m and m.start() > 0:
            s = s[: m.start()].strip()
        if is_china_trim_like_noise(s):
            return ""
    if meili_attr == "generation" and is_china_trim_like_noise(s):
        return ""
    s = re.sub(r"^([A-Za-z0-9&\-]+)\s+\1\b", r"\1", s, flags=re.IGNORECASE)
    return s


@lru_cache(maxsize=1)
def _trim_synonyms_by_canon() -> Dict[str, frozenset[str]]:
    a = {k: set(v) for k, v in _invert_en_domain("trim_name").items()}
    for k, vs in _invert_en_domain("configuration").items():
        a.setdefault(k, set()).update(vs)
    return {k: frozenset(v) for k, v in a.items()}


def _canon_ru_fuel(raw: str) -> str:
    s = _as_text(raw)
    if not s:
        return ""
    hit = _FUEL_CANON_ALIASES.get(s)
    if hit:
        return hit
    m = _ru_engine_type_map()
    if s in m:
        return m[s]
    return s


def _canon_ru_body(raw: str) -> str:
    return _ru_body_type_map().get(_as_text(raw), _as_text(raw))


def _canon_ru_color(raw: str) -> str:
    return _ru_color_map().get(_as_text(raw), _as_text(raw))


def _canon_ru_transmission(raw: str) -> str:
    s = _as_text(raw)
    if not s:
        return ""
    m = _ru_transmission_map()
    if s in m:
        return m[s]
    u = s.upper()
    if u == "CVT":
        return "Вариатор"
    if u in ("AT", "A/T"):
        return "Автомат"
    if u in ("MT", "M/T"):
        return "Механика"
    return s


def _should_drop_transmission_facet(value: str) -> bool:
    s = _as_text(value)
    if not s:
        return True
    if _JUNK_TRANS_NUMERIC.match(s):
        return True
    return False


def merge_facet_distribution_rows(
    meili_attr: str,
    rows: List[Dict[str, object]],
    *,
    query_flat: Optional[Dict[str, str]],
) -> List[Dict[str, object]]:
    if not rows:
        return []
    korea = is_korea_catalog_flat(query_flat)
    china = is_china_catalog_flat(query_flat)
    china_main_dims = {"brand", "model_group", "generation", "trim"}
    if not korea:
        if china and meili_attr in china_main_dims:
            grouped: Dict[str, Dict[str, object]] = {}
            for r in rows:
                raw = _as_text(r.get("value"))
                count = int(r.get("count") or 0)
                if not raw or count <= 0:
                    continue
                label = _cleanup_china_facet_value(raw, meili_attr) or raw
                key = re.sub(r"\s+", " ", label.strip().lower())
                if not key:
                    continue
                bucket = grouped.get(key)
                if bucket is None:
                    bucket = {
                        "value": raw,  # первичный raw для обратной совместимости
                        "label": label,
                        "values": [raw],
                        "count": 0,
                    }
                    grouped[key] = bucket
                else:
                    vals = bucket.get("values")
                    if isinstance(vals, list) and raw not in vals:
                        vals.append(raw)
                bucket["count"] = int(bucket.get("count") or 0) + count
            out_cn = list(grouped.values())
            out_cn.sort(key=lambda r: str(r.get("label") or r.get("value") or "").lower())
            return out_cn
        out = [{"value": str(r["value"]), "count": int(r["count"])} for r in rows if int(r.get("count") or 0) > 0]
        out.sort(key=lambda r: str(r["value"]).lower())
        return out

    acc: Dict[str, int] = defaultdict(int)
    for r in rows:
        raw = _as_text(r.get("value"))
        if not raw or int(r.get("count") or 0) <= 0:
            continue
        if meili_attr == "transmission" and _should_drop_transmission_facet(raw):
            continue
        if meili_attr == "fuel":
            key = _canon_ru_fuel(raw)
        elif meili_attr == "body_type":
            key = _canon_ru_body(raw)
        elif meili_attr == "color":
            key = _canon_ru_color(raw)
        elif meili_attr == "transmission":
            key = _canon_ru_transmission(raw)
        elif meili_attr == "brand":
            key = facet_canonical_english(raw, "mark")
        elif meili_attr == "model_group":
            key = facet_canonical_english(raw, "model")
        elif meili_attr == "generation":
            key = facet_canonical_english(raw, "generation")
        elif meili_attr == "trim":
            key = facet_canonical_english(raw, "trim_name")
        else:
            key = raw
        if not key:
            continue
        if korea and _KO_OR_ZH_RE.search(key):
            continue
        acc[key] += int(r["count"])

    merged = [{"value": k, "count": int(v)} for k, v in acc.items() if k and int(v) > 0]
    merged.sort(key=lambda r: str(r["value"]).lower())
    return merged


def expand_filter_values(meili_attr: str, values: Sequence[str], *, query_flat: Optional[Dict[str, str]]) -> List[str]:
    out: List[str] = []
    if not values:
        return out
    korea = is_korea_catalog_flat(query_flat)
    china = is_china_catalog_flat(query_flat)
    if not korea:
        if china and meili_attr in {"brand", "model_group", "generation", "trim"}:
            # Для China-фасетов в UI хранится raw value из Meili, не расширяем,
            # чтобы не терять связку бренд→модель→поколение→комплектация.
            return [str(v).strip() for v in values if str(v).strip()]
        return [str(v).strip() for v in values if str(v).strip()]

    for v in values:
        s = str(v).strip()
        if not s:
            continue
        if meili_attr == "brand":
            c = facet_canonical_english(s, "mark")
            bag = _brand_synonyms_by_canon().get(c) or frozenset({s, c})
            out.extend(bag)
        elif meili_attr == "model_group":
            c = facet_canonical_english(s, "model")
            bag = _invert_en_domain("model").get(c) or frozenset({s, c})
            out.extend(bag)
        elif meili_attr == "generation":
            c = facet_canonical_english(s, "generation")
            bag = _invert_en_domain("generation").get(c) or frozenset({s, c})
            out.extend(bag)
        elif meili_attr == "trim":
            c = facet_canonical_english(s, "trim_name")
            bag = _trim_synonyms_by_canon().get(c) or frozenset({s, c})
            out.extend(bag)
        elif meili_attr == "fuel":
            c = _canon_ru_fuel(s)
            bag = _fuel_synonyms_by_canon().get(c) or frozenset({s, c})
            out.extend(bag)
        elif meili_attr == "body_type":
            c = _canon_ru_body(s)
            bag = _body_synonyms_by_canon().get(c) or frozenset({s, c})
            out.extend(bag)
        elif meili_attr == "color":
            c = _canon_ru_color(s)
            bag = _color_synonyms_by_canon().get(c) or frozenset({s, c})
            out.extend(bag)
        elif meili_attr == "transmission":
            c = _canon_ru_transmission(s)
            bag = _trans_synonyms_by_canon().get(c) or frozenset({s, c})
            out.extend(bag)
        else:
            out.append(s)

    seen: set[str] = set()
    dedup: List[str] = []
    for x in out:
        t = str(x).strip()
        if not t or t in seen:
            continue
        seen.add(t)
        dedup.append(t)
    return dedup
