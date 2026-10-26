"""Korea HP (л.с.) + torque (Н·м): listing text, sibling consensus, engine_map.

No LLM. Excise/util fee cannot be guessed from displacement alone — only values
backed by an explicit listing string, a tight peer majority, or the curated
engine_map.json are applied.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, Mapping, Optional, Tuple

from encar_mapping_lookup import encar_mapping_en_for
from hp_catalog_store import normalize_key_part

HP_MIN = 20
HP_MAX = 2500
NM_MIN = 50
NM_MAX = 1500
KGM_TO_NM = 9.80665

_HP_MA_RE = re.compile(r"(\d{2,4})\s*마력")
_HP_UNIT_RE = re.compile(r"(\d{2,4})\s*(?:ps|hp)\b", re.IGNORECASE)
_HP_PAREN_RE = re.compile(r"\(\s*(\d{2,4})\s*\)\s*hp\b", re.IGNORECASE)
_NM_RE = re.compile(r"(\d{2,4}(?:[.,]\d+)?)\s*(?:n[\s·.•]*m|нм)\b", re.IGNORECASE)
_KGM_RE = re.compile(
    r"(\d{1,3}(?:[.,]\d+)?)\s*(?:kg[\s·.•]*m|kgm|кг[\s·.•]*м)\b",
    re.IGNORECASE,
)

_TEXT_FIELDS = (
    "generation",
    "trim_name",
    "gradeName",
    "configuration",
    "title",
    "modelName",
    "model",
    "displacement_label",
    "engine",
    "badge",
)


def parse_hp(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        hp = int(round(float(value)))
        return hp if HP_MIN <= hp <= HP_MAX else None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        return None
    try:
        hp = int(digits)
    except ValueError:
        return None
    return hp if HP_MIN <= hp <= HP_MAX else None


def parse_nm(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        nm = int(round(float(value)))
        return nm if NM_MIN <= nm <= NM_MAX else None
    raw = str(value).strip().replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)", raw)
    if not m:
        return None
    try:
        nm = int(round(float(m.group(1))))
    except ValueError:
        return None
    return nm if NM_MIN <= nm <= NM_MAX else None


def _kgm_to_nm(kgm: float) -> Optional[int]:
    if kgm < 5 or kgm > 160:
        return None
    nm = int(round(kgm * KGM_TO_NM))
    return nm if NM_MIN <= nm <= NM_MAX else None


def extract_hp_from_text(text: Any) -> Optional[int]:
    s = str(text or "")
    if not s.strip():
        return None
    for rx in (_HP_MA_RE, _HP_PAREN_RE, _HP_UNIT_RE):
        m = rx.search(s)
        if m:
            hp = parse_hp(m.group(1))
            if hp is not None:
                return hp
    return None


def extract_nm_from_text(text: Any) -> Optional[int]:
    s = str(text or "")
    if not s.strip():
        return None
    m_nm = _NM_RE.search(s)
    if m_nm:
        try:
            nm = int(round(float(m_nm.group(1).replace(",", "."))))
        except ValueError:
            nm = None
        if nm is not None and NM_MIN <= nm <= NM_MAX:
            return nm
    m_kg = _KGM_RE.search(s)
    if m_kg:
        try:
            kgm = float(m_kg.group(1).replace(",", "."))
        except ValueError:
            return None
        return _kgm_to_nm(kgm)
    return None


def fuel_bucket(raw: Any) -> str:
    ko = str(raw or "")
    s = ko.strip().lower()
    if not s:
        return ""
    if (
        "하이브리드" in ko
        or "hybrid" in s
        or "hev" in s
        or "phev" in s
        or "гибрид" in s
        or ("가솔린" in ko and "전기" in ko)
        or ("디젤" in ko and "전기" in ko)
        or ("gasoline" in s and "electric" in s)
        or ("diesel" in s and "electric" in s)
    ):
        return "hybrid"
    if "전기" in ko or "electric" in s or "электро" in s:
        return "electric"
    if "디젤" in ko or "diesel" in s or "дизел" in s:
        return "diesel"
    if "lpg" in s or "엘피지" in ko or "가스" in ko:
        return "lpg"
    if "수소" in ko or "hydrogen" in s:
        return "hydrogen"
    return "gas"


def cc_bucket(cc: Any) -> Optional[int]:
    try:
        n = int(cc)
    except (TypeError, ValueError):
        return None
    if n < 500 or n > 10000:
        return None
    return int(round(n / 100.0) * 100)


def canon_mark(raw: Any) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    en = encar_mapping_en_for("mark", s)
    return normalize_key_part(en or s)


def canon_model(raw: Any, group: Any = "") -> str:
    s = str(raw or "").strip()
    g = str(group or "").strip()
    en = encar_mapping_en_for("model", s) if s else ""
    if not en and g:
        en = encar_mapping_en_for("model", g)
    return normalize_key_part(en or s or g)


def canon_generation(raw: Any) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    en = encar_mapping_en_for("generation", s)
    return normalize_key_part(en or s)


def turbo_flag(row: Mapping[str, Any]) -> bool:
    blob = {
        "engine_type": row.get("fuel_type") or row.get("engine_type"),
        "generation": row.get("generation"),
        "gradeName": row.get("trim_name") or row.get("gradeName"),
        "configuration": row.get("configuration"),
        "model": row.get("model"),
        "modelName": row.get("modelName") or row.get("model"),
        "modelGroupName": row.get("encar_model_group") or row.get("modelGroupName"),
        "mark": row.get("mark"),
    }
    try:
        from engine_hp_resolver import detect_turbo

        return bool(detect_turbo(blob))
    except Exception:
        return False


def _iter_text_blobs(payload: Mapping[str, Any]) -> Iterator[str]:
    nodes: list[Any] = [payload]
    inner = payload.get("data")
    if isinstance(inner, dict):
        nodes.append(inner)
    for node in nodes:
        if not isinstance(node, dict):
            continue
        for key in _TEXT_FIELDS:
            v = node.get(key)
            if v not in (None, ""):
                yield str(v)
        spec = node.get("spec_clean")
        if isinstance(spec, dict):
            for key in ("power_hp", "torque_nm", "displacement_label", "engine"):
                v = spec.get(key)
                if v not in (None, ""):
                    yield str(v)
        spec_raw = node.get("spec")
        if isinstance(spec_raw, dict):
            for key in spec_raw.values():
                if isinstance(key, (str, int, float)):
                    yield str(key)


def extract_hp_torque_from_payload(payload: Mapping[str, Any]) -> Tuple[Optional[int], Optional[int], str]:
    """Explicit HP/Nm already stored or written as 마력 / kg·m / N·m in listing text."""
    nodes: list[dict] = []
    if isinstance(payload, dict):
        nodes.append(payload)
        inner = payload.get("data")
        if isinstance(inner, dict):
            nodes.append(inner)

    hp = None
    nm = None
    for node in nodes:
        if hp is None:
            for key in ("power", "power_hp", "hp", "outputHorsepower", "horsepower"):
                hp = parse_hp(node.get(key))
                if hp is not None:
                    break
        if nm is None:
            for key in ("torque_nm", "max_torque_nm", "torque", "outputTorque"):
                nm = parse_nm(node.get(key))
                if nm is not None:
                    break
        spec = node.get("spec_clean")
        if isinstance(spec, dict):
            if hp is None:
                hp = parse_hp(spec.get("power_hp") or spec.get("power"))
            if nm is None:
                nm = parse_nm(spec.get("torque_nm") or spec.get("torque"))

    src = "listing_field" if (hp or nm) else ""
    if hp is not None and nm is not None:
        return hp, nm, src or "listing_field"

    for blob in _iter_text_blobs(payload):
        if hp is None:
            got = extract_hp_from_text(blob)
            if got is not None:
                hp = got
                src = src or "listing_text"
        if nm is None:
            got_n = extract_nm_from_text(blob)
            if got_n is not None:
                nm = got_n
                src = src or "listing_text"
        if hp is not None and nm is not None:
            break
    return hp, nm, src


def _targets_for_payload(payload: Dict[str, Any]) -> list[dict]:
    out = [payload]
    inner = payload.get("data")
    if isinstance(inner, dict) and inner is not payload:
        out.append(inner)
    return out


def apply_hp_torque(
    payload: Dict[str, Any],
    *,
    hp: Optional[int],
    nm: Optional[int],
    source: str,
) -> bool:
    """Write HP/Nm onto wrapper + inner data + spec_clean. Returns True if anything changed."""
    if not isinstance(payload, dict):
        return False
    changed = False
    for node in _targets_for_payload(payload):
        if hp is not None:
            if str(node.get("power") or "").strip() != str(hp):
                node["power"] = str(hp)
                changed = True
            if node.get("power_hp") != hp:
                node["power_hp"] = hp
                changed = True
            if source and node.get("power_source") != source:
                node["power_source"] = source
                changed = True
        if nm is not None:
            if node.get("torque_nm") != nm:
                node["torque_nm"] = nm
                changed = True
            if node.get("max_torque_nm") != nm:
                node["max_torque_nm"] = nm
                changed = True
        spec = node.get("spec_clean")
        if isinstance(spec, dict):
            if hp is not None and spec.get("power_hp") != hp:
                spec["power_hp"] = hp
                changed = True
            if nm is not None and spec.get("torque_nm") != nm:
                spec["torque_nm"] = nm
                changed = True
    return changed


def enrich_payload_from_listing_text(data: Dict[str, Any]) -> None:
    """Cheap per-card fill used by catalog sync: only explicit listing strings/fields."""
    if not isinstance(data, dict):
        return
    hp, nm, src = extract_hp_torque_from_payload(data)
    if hp is None and nm is None:
        return
    apply_hp_torque(data, hp=hp, nm=nm, source=src or "listing_text")


def engine_map_hp(row: Mapping[str, Any]) -> Optional[int]:
    blob = {
        "mark": row.get("mark"),
        "manufacturerName": row.get("mark"),
        "model": row.get("model"),
        "modelName": row.get("model"),
        "modelGroupName": row.get("encar_model_group") or row.get("modelGroupName"),
        "generation": row.get("generation"),
        "gradeName": row.get("trim_name") or row.get("gradeName"),
        "configuration": row.get("configuration") or row.get("generation"),
        "engine_type": row.get("fuel_type") or row.get("engine_type"),
        "displacement": row.get("displacement_cc") or row.get("displacement"),
        "displacement_cc": row.get("displacement_cc") or row.get("displacement"),
        "year": row.get("year"),
        "yearMonth": row.get("year_month") or row.get("year"),
    }
    try:
        from engine_hp_resolver import resolve_engine_hp

        return resolve_engine_hp(blob, record_source=False)
    except Exception:
        return None


FamilyKey = Tuple[str, str, int, str, int, int]
NoyKey = Tuple[str, str, int, str, int]
GenKey = Tuple[str, str, int, str, int, int, str]
MotorKey = Tuple[str, int, str]


def motor_code_of(row: Mapping[str, Any]) -> str:
    raw = row.get("motor_code") or row.get("motorType") or row.get("motor_type") or ""
    if raw:
        return re.sub(r"\s+", "", str(raw).strip().upper())
    try:
        from engine_hp_resolver import extract_motor_code
    except ImportError:
        return ""
    blobs: list[Any] = [row]
    inner = row.get("data") if isinstance(row.get("data"), dict) else None
    if isinstance(inner, dict):
        blobs.append(inner)
    for blob in blobs:
        if not isinstance(blob, dict):
            continue
        code = extract_motor_code(blob)
        if code:
            return code
        nested = blob.get("data")
        if isinstance(nested, dict):
            code = extract_motor_code(nested)
            if code:
                return code
    return ""


def _accept_motor(counter: Counter[int], *, kind: str) -> Optional[int]:
    """OEM motorType is the engine identity — a single clean observation is enough."""
    hit = _accept(counter, kind=kind)
    if hit is not None:
        return hit
    if not counter or len(counter) != 1:
        return None
    val, n = counter.most_common(1)[0]
    if n < 1:
        return None
    if kind == "hp" and 50 <= val <= 700:
        return val
    if kind == "nm" and 80 <= val <= 900:
        return val
    return None


def _accept(counter: Counter[int], *, kind: str) -> Optional[int]:
    if not counter:
        return None
    val, n = counter.most_common(1)[0]
    total = sum(counter.values())
    if n <= 0 or total <= 0:
        return None
    share = n / total
    lo, hi = (HP_MIN, HP_MAX) if kind == "hp" else (NM_MIN, NM_MAX)
    if not (lo <= val <= hi):
        return None
    if n >= 2 and n == total:
        return val
    if n >= 3 and share >= 0.75:
        return val
    if n >= 10 and share >= 0.65:
        return val
    return None


@dataclass
class ConsensusHit:
    hp: Optional[int] = None
    nm: Optional[int] = None
    source: str = ""
    hp_votes: int = 0
    nm_votes: int = 0


@dataclass
class KoreaPowerConsensus:
    year_hp: dict[FamilyKey, Counter[int]] = field(default_factory=lambda: defaultdict(Counter))
    year_nm: dict[FamilyKey, Counter[int]] = field(default_factory=lambda: defaultdict(Counter))
    gen_hp: dict[GenKey, Counter[int]] = field(default_factory=lambda: defaultdict(Counter))
    gen_nm: dict[GenKey, Counter[int]] = field(default_factory=lambda: defaultdict(Counter))
    noy_hp: dict[NoyKey, Counter[int]] = field(default_factory=lambda: defaultdict(Counter))
    noy_nm: dict[NoyKey, Counter[int]] = field(default_factory=lambda: defaultdict(Counter))
    motor_hp: dict[MotorKey, Counter[int]] = field(default_factory=lambda: defaultdict(Counter))
    motor_nm: dict[MotorKey, Counter[int]] = field(default_factory=lambda: defaultdict(Counter))
    observations: int = 0

    def motor_key(self, row: Mapping[str, Any]) -> Optional[MotorKey]:
        code = motor_code_of(row)
        if not code or len(code) < 3:
            return None
        cc = cc_bucket(row.get("displacement_cc") or row.get("displacement"))
        fuel = fuel_bucket(row.get("fuel_type") or row.get("engine_type"))
        if cc is None or not fuel:
            return None
        return (code, cc, fuel)

    def family_parts(self, row: Mapping[str, Any]) -> Optional[Tuple[FamilyKey, NoyKey, GenKey]]:
        mark = canon_mark(row.get("mark"))
        model = canon_model(row.get("model"), row.get("encar_model_group") or row.get("modelGroupName"))
        cc = cc_bucket(row.get("displacement_cc") or row.get("displacement"))
        fuel = fuel_bucket(row.get("fuel_type") or row.get("engine_type"))
        try:
            year = int(row.get("year") or 0)
        except (TypeError, ValueError):
            year = 0
        if year > 2100:
            year = year // 100
        if not (1980 <= year <= 2035):
            ym = row.get("year_month") or row.get("yearMonth") or ""
            digits = "".join(ch for ch in str(ym) if ch.isdigit())
            if len(digits) >= 4:
                try:
                    year = int(digits[:4])
                except ValueError:
                    year = 0
        if not mark or not model or cc is None or not fuel or not (1980 <= year <= 2035):
            return None
        turbo = 1 if turbo_flag(row) else 0
        gen = canon_generation(row.get("generation"))
        fk: FamilyKey = (mark, model, cc, fuel, year, turbo)
        nk: NoyKey = (mark, model, cc, fuel, turbo)
        gk: GenKey = (mark, model, cc, fuel, year, turbo, gen)
        return fk, nk, gk

    def add_observation(self, row: Mapping[str, Any], *, hp: Optional[int] = None, nm: Optional[int] = None) -> None:
        mk = self.motor_key(row)
        if mk is not None:
            if hp is not None:
                self.motor_hp[mk][hp] += 1
            if nm is not None:
                self.motor_nm[mk][nm] += 1
        parts = self.family_parts(row)
        if parts is None:
            if hp is not None and mk is not None:
                self.observations += 1
            return
        fk, nk, gk = parts
        if hp is not None:
            self.year_hp[fk][hp] += 1
            self.noy_hp[nk][hp] += 1
            if gk[-1]:
                self.gen_hp[gk][hp] += 1
            self.observations += 1
        if nm is not None:
            self.year_nm[fk][nm] += 1
            self.noy_nm[nk][nm] += 1
            if gk[-1]:
                self.gen_nm[gk][nm] += 1

    def _near_year(self, store: Mapping[FamilyKey, Counter[int]], fk: FamilyKey, kind: str) -> Optional[int]:
        mark, model, cc, fuel, year, turbo = fk
        left = _accept(store.get((mark, model, cc, fuel, year - 1, turbo), Counter()), kind=kind)
        right = _accept(store.get((mark, model, cc, fuel, year + 1, turbo), Counter()), kind=kind)
        if left is not None and right is not None:
            return left if left == right else None
        return left if left is not None else right

    def resolve(self, row: Mapping[str, Any]) -> ConsensusHit:
        hit = ConsensusHit()
        listing_hp, listing_nm, listing_src = extract_hp_torque_from_payload(row)
        if listing_hp is not None:
            hit.hp = listing_hp
            hit.source = listing_src or "listing_text"
        if listing_nm is not None:
            hit.nm = listing_nm
            if not hit.source:
                hit.source = listing_src or "listing_text"

        parts = self.family_parts(row)
        fk: Optional[FamilyKey]
        nk: Optional[NoyKey]
        gk: Optional[GenKey]
        if parts is None:
            fk = nk = gk = None
        else:
            fk, nk, gk = parts

        def _fill(kind: str) -> None:
            cur = hit.hp if kind == "hp" else hit.nm
            if cur is not None:
                return
            gen_store = self.gen_hp if kind == "hp" else self.gen_nm
            year_store = self.year_hp if kind == "hp" else self.year_nm
            noy_store = self.noy_hp if kind == "hp" else self.noy_nm
            motor_store = self.motor_hp if kind == "hp" else self.motor_nm
            accepted = None
            src = ""
            votes = 0
            mk = self.motor_key(row)
            if mk is not None:
                c = motor_store.get(mk, Counter())
                accepted = _accept_motor(c, kind=kind)
                if accepted is not None:
                    src = "peer_motor"
                    votes = c[accepted]
            if accepted is None and gk is not None and gk[-1]:
                c = gen_store.get(gk, Counter())
                accepted = _accept(c, kind=kind)
                if accepted is not None:
                    src = "peer_generation"
                    votes = c[accepted]
            if accepted is None and fk is not None:
                c = year_store.get(fk, Counter())
                accepted = _accept(c, kind=kind)
                if accepted is not None:
                    src = "peer_year"
                    votes = c[accepted]
            if accepted is None and fk is not None:
                accepted = self._near_year(year_store, fk, kind)
                if accepted is not None:
                    src = "peer_year_near"
                    votes = 0
            if accepted is None and nk is not None:
                c = noy_store.get(nk, Counter())
                accepted = _accept(c, kind=kind)
                if accepted is not None:
                    src = "peer_family"
                    votes = c[accepted]
            if accepted is None:
                mapped = engine_map_hp(row) if kind == "hp" else None
                if mapped is not None:
                    year_c = year_store.get(fk, Counter()) if fk is not None else Counter()
                    noy_c = noy_store.get(nk, Counter()) if nk is not None else Counter()
                    if mapped in year_c or mapped in noy_c or (not year_c and not noy_c):
                        accepted = mapped
                        src = "engine_map"
                        votes = int(year_c.get(mapped, 0) + noy_c.get(mapped, 0))
            if accepted is None:
                return
            if kind == "hp":
                hit.hp = accepted
                hit.hp_votes = votes
            else:
                hit.nm = accepted
                hit.nm_votes = votes
            if not hit.source:
                hit.source = src

        _fill("hp")
        _fill("nm")
        if hit.hp is None:
            mapped = engine_map_hp(row)
            if mapped is not None:
                hit.hp = mapped
                hit.source = hit.source or "engine_map"
        return hit

    def coverage_preview(self, rows: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
        stats = Counter()
        for row in rows:
            has_hp = parse_hp(row.get("power_hp")) is not None
            has_nm = parse_nm(row.get("torque_nm")) is not None
            stats["rows"] += 1
            if has_hp:
                stats["have_hp"] += 1
            if has_nm:
                stats["have_nm"] += 1
            if has_hp and has_nm:
                continue
            hit = self.resolve(row)
            if not has_hp and hit.hp is not None:
                stats["fill_hp"] += 1
                stats[f"hp_{hit.source or 'unknown'}"] += 1
            if not has_nm and hit.nm is not None:
                stats["fill_nm"] += 1
            if (has_hp or hit.hp is not None) and (has_nm or hit.nm is not None):
                stats["after_both"] += 1
            elif has_hp or hit.hp is not None:
                stats["after_hp_only"] += 1
            if not has_hp and hit.hp is None:
                stats["unresolved_hp"] += 1
                parts = self.family_parts(row)
                fuel = fuel_bucket(row.get("fuel_type") or row.get("engine_type"))
                if fuel in {"hybrid", "electric"}:
                    stats["skip_hybrid_ev"] += 1
                elif parts is None:
                    if not canon_mark(row.get("mark")):
                        stats["skip_no_mark"] += 1
                    elif not canon_model(row.get("model"), row.get("encar_model_group")):
                        stats["skip_no_model"] += 1
                    elif cc_bucket(row.get("displacement_cc") or row.get("displacement")) is None:
                        stats["skip_no_cc"] += 1
                    else:
                        stats["skip_no_year_or_fuel"] += 1
                else:
                    fk, nk, _gk = parts
                    year_c = self.year_hp.get(fk, Counter())
                    noy_c = self.noy_hp.get(nk, Counter())
                    if year_c and _accept(year_c, kind="hp") is None:
                        stats["skip_year_conflict"] += 1
                    elif noy_c and _accept(noy_c, kind="hp") is None:
                        stats["skip_family_conflict"] += 1
                    elif not year_c and not noy_c:
                        stats["skip_no_peers"] += 1
                    else:
                        stats["skip_other"] += 1
        return dict(stats)


def thin_row_to_payload_stub(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Enough fields for extract/engine_map/consensus without the full JSONB."""
    return {
        "mark": row.get("mark"),
        "model": row.get("model"),
        "encar_model_group": row.get("encar_model_group"),
        "modelGroupName": row.get("encar_model_group"),
        "generation": row.get("generation"),
        "trim_name": row.get("trim_name"),
        "gradeName": row.get("trim_name"),
        "fuel_type": row.get("fuel_type"),
        "engine_type": row.get("fuel_type"),
        "displacement_cc": row.get("displacement_cc"),
        "displacement": row.get("displacement_cc"),
        "year": row.get("year"),
        "year_month": row.get("year_month") or row.get("year"),
        "power_hp": row.get("power_hp"),
        "torque_nm": row.get("torque_nm"),
        "motor_code": row.get("motor_code") or row.get("motorType"),
    }
