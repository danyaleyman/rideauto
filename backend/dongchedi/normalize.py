"""SKU из API + опционально skuDetail → документ для cars.data_json."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from localization.term_localizer import facet_canonical_english

_WAN_KM_RE = re.compile(r"([\d.]+)\s*万\s*公里")
_PLAIN_KM_RE = re.compile(r"(?<![\d.])(\d{3,7})\s*公里")
_WAN_PRICE_RE = re.compile(r"([\d]+(?:\.[\d]+)?)\s*万")
_HP_RE = re.compile(r"(\d+)\s*马力")
_HP_PS_RE = re.compile(r"(\d+)\s*ps", re.IGNORECASE)
_POWER_KW_RE = re.compile(r"(\d{2,4})(?:\s*\(\s*\d+\s*Ps\s*\))?")
_TORQUE_NM_RE = re.compile(r"(\d{2,5})")
_TRANSFER_CNT_RE = re.compile(r"(\d+)\s*次")
_REG_YM_RE = re.compile(r"(\d{4})年\s*(\d{1,2})\s*月")
_TITLE_YEAR_RE = re.compile(r"^\s*(\d{4})\s*款\s*")
_DISP_LABEL_RE = re.compile(r"(\d(?:\.\d)?)\s*[TL]")
_CHINA_STATIC_MAPS: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None


def _utc_date_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _fen_to_cny(fen: Any) -> Optional[float]:
    try:
        v = int(fen)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return v / 100.0


def _parse_wan_price_text(s: str) -> Optional[float]:
    if not s or not str(s).strip():
        return None
    m = _WAN_PRICE_RE.search(str(s))
    if not m:
        return None
    try:
        return float(m.group(1)) * 10000.0
    except ValueError:
        return None


def _km_from_mileage_str(raw: str) -> Optional[int]:
    """«6.68万公里» / «6.68万 公里» / «66800公里» → км (целое)."""
    if not raw:
        return None
    s = str(raw).strip()
    m = _WAN_KM_RE.search(s)
    if m:
        try:
            return int(float(m.group(1)) * 10000)
        except ValueError:
            return None
    m = _PLAIN_KM_RE.search(s)
    if m:
        try:
            v = int(m.group(1))
            if 100 <= v <= 3_000_000:
                return v
        except ValueError:
            return None
    return None


def _km_from_car_info_mileage_value(raw: Any) -> Optional[int]:
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        try:
            v = int(raw)
        except (TypeError, ValueError):
            return None
        if 300 <= v <= 2_000_000:
            return v
        return None
    return _km_from_mileage_str(str(raw))


def _km_from_param_pairs(params: Dict[str, str]) -> Optional[int]:
    for key in ("行驶里程", "里程", "表显里程", "公里数"):
        pv = params.get(key)
        if pv:
            k = _km_from_mileage_str(str(pv))
            if k is not None:
                return k
    return None


_DETAIL_STR_KEYS_FOR_KM = (
    "important_text",
    "subtitle",
    "share_title",
    "seo_description",
    "description",
    "brief",
)

_KM_WALK_SKIP_KEYS = frozenset(
    {
        "image_list",
        "head_images",
        "pics",
        "images",
        "url",
        "image",
        "avatar",
        "icon",
        "logo",
    }
)


def _km_from_detail_known_strings(detail: Optional[Dict[str, Any]]) -> Optional[int]:
    if not detail or not isinstance(detail, dict):
        return None
    for k in _DETAIL_STR_KEYS_FOR_KM:
        v = detail.get(k)
        if isinstance(v, str) and v.strip():
            k0 = _km_from_mileage_str(v)
            if k0 is not None:
                return k0
    return None


def _km_walk_detail_for_mileage(obj: Any, depth: int = 0) -> Optional[int]:
    """Последний fallback: любой короткий фрагмент JSON карточки с «万公里»."""
    if depth > 12 or obj is None:
        return None
    if isinstance(obj, str):
        if len(obj) > 800:
            return None
        return _km_from_mileage_str(obj)
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _KM_WALK_SKIP_KEYS:
                continue
            r = _km_walk_detail_for_mileage(v, depth + 1)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for i, it in enumerate(obj):
            if i > 120:
                break
            r = _km_walk_detail_for_mileage(it, depth + 1)
            if r is not None:
                return r
    return None


def _param_pairs_from_detail(detail: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Собирает name→value из other_params / important_params карточки Dongchedi."""
    out: Dict[str, str] = {}
    if not detail or not isinstance(detail, dict):
        return out
    for key in ("other_params", "important_params"):
        raw = detail.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            val = str(item.get("value") or "").strip()
            if name and val and len(name) < 80 and len(val) < 200:
                out[name] = val
    return out


def _highlight_options_from_detail(detail: Optional[Dict[str, Any]]) -> list[str]:
    """
    Опции из блока 推荐理由/亮点配置.
    В skuDetail обычно приходят как high_light_config[].name.
    """
    if not detail or not isinstance(detail, dict):
        return []
    raw = detail.get("high_light_config")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(item or "").strip()
        if not name or len(name) > 80 or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _parse_register_year_month(s: str) -> tuple[str, str]:
    """'2019年06月' → ('2019', '201906'). Пустые строки если не распознано."""
    m = _REG_YM_RE.search(s or "")
    if not m:
        return "", ""
    y, mo = m.group(1), m.group(2).zfill(2)
    return y, f"{y}{mo}"


def _parse_horsepower_ma(s: Any) -> Optional[int]:
    raw = str(s or "")
    m = _HP_RE.search(raw)
    if not m:
        m = _HP_PS_RE.search(raw)
    if not m:
        return None
    try:
        hp = int(m.group(1))
    except ValueError:
        return None
    return hp if 20 <= hp <= 2000 else None


def _parse_transfer_times(s: str) -> Optional[int]:
    m = _TRANSFER_CNT_RE.search(s or "")
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _parse_power_kw_text(s: Any) -> Optional[int]:
    raw = str(s or "").strip()
    if not raw:
        return None
    m = _POWER_KW_RE.search(raw)
    if not m:
        return None
    try:
        kw = int(m.group(1))
    except ValueError:
        return None
    return kw if 20 <= kw <= 1600 else None


def _parse_torque_nm_text(s: Any) -> Optional[int]:
    raw = str(s or "").strip()
    if not raw:
        return None
    m = _TORQUE_NM_RE.search(raw)
    if not m:
        return None
    try:
        nm = int(m.group(1))
    except ValueError:
        return None
    return nm if 40 <= nm <= 3000 else None


def _split_generation_and_trim(text: str) -> tuple[str, str]:
    """
    "2019款 升级款 2.0T 旗舰型 国VI" -> ("升级款", "2.0T 旗舰型 国VI")
    "超长续航智驾版" -> ("", "超长续航智驾版")
    """
    src = str(text or "").strip()
    if not src:
        return "", ""
    s = _TITLE_YEAR_RE.sub("", src).strip()
    if not s:
        return "", ""
    m = _DISP_LABEL_RE.search(s.upper())
    if not m:
        return "", s
    cut = m.start()
    left = s[:cut].strip()
    right = s[cut:].strip()
    return left, right or s


def _displacement_cc_from_label(s: str) -> Optional[str]:
    """Только если явно в см³ (цифры ~800–8000); иначе None — текст в dongchedi_displacement_label."""
    t = str(s or "").strip().replace(" ", "")
    if not t:
        return None
    if "T" in t.upper() or t.endswith("L") or "升" in t:
        return None
    digits = re.sub(r"[^\d]", "", t)
    if not digits:
        return None
    try:
        n = int(digits)
    except ValueError:
        return None
    if 800 <= n <= 8000:
        return str(n)
    return None


def _img_url_canonical(u: str) -> str:
    s = (u or "").strip()
    if not s:
        return ""
    if s.startswith("//"):
        return "https:" + s
    return s


def _is_likely_noise_image_url(u: str) -> bool:
    low = (u or "").lower()
    if not low:
        return True
    # Служебные/маркетинговые ассеты. Не отсекать по tplv-dcdx-* и tos-cn путям целиком —
    # в реальных URL галереи ByteDance часто те же подстроки, иначе в БД остаётся одна обложка.
    if any(
        x in low
        for x in (
            "/motor-mis-img/",
            "watermark",
            "banner",
            "poster",
            "/favicon",
            "favicon.ico",
        )
    ):
        return True
    if "icon" in low and ("/icon" in low or "icon_" in low or "icons/" in low):
        return True
    if "logo" in low and ("/logo" in low or "logo_" in low or "brand_logo" in low):
        return True
    # Очень часто повторяющиеся плейсхолдеры/иконки в выдаче.
    if any(
        x in low
        for x in (
            "5e2599cc0a064530991965858af6481f",
            "e2fc38eaccfb4da2bb999d8bca3db023",
            "e955c93eeeeb4788933e412b08c76f18",
        )
    ):
        return True
    return False


def _first_nonempty_str(*vals: Any) -> str:
    for v in vals:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def _deep_collect_image_urls(detail: Dict[str, Any], *, max_urls: int = 80) -> list[str]:
    """Рекурсивно вытаскивает URL картинок из skuDetail (__NEXT_DATA__): галереи часто вложены."""

    out: list[str] = []
    dup: set[str] = set()

    def looks_like_photo_url(low: str) -> bool:
        if _is_likely_noise_image_url(low):
            return False
        return any(
            x in low
            for x in (
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".gif",
                "byteimg",
                "bytecdn",
                "dcdapp",
                "dcd-cdn",
                "p3-dcd",
                "p9-dcd",
                "p6-dcd",
                "tos-cn",
                "dcarimg",
                "dcarstatic",
                "motor.sh",
                "sh.image",
                "/image",
            )
        )

    def walk(o: Any, depth: int) -> None:
        if depth > 18 or len(out) >= max_urls:
            return
        if isinstance(o, str):
            s = _img_url_canonical(o)
            if len(s) < 20 or not s.startswith("http"):
                return
            low = s.lower()
            if s in dup or not looks_like_photo_url(low):
                return
            dup.add(s)
            out.append(s)
            return
        if isinstance(o, dict):
            for v in o.values():
                walk(v, depth + 1)
        elif isinstance(o, list):
            for v in o[:500]:
                walk(v, depth + 1)

    walk(detail, 0)
    return out


def _image_urls_from_row_and_detail(
    row_img: str,
    detail: Optional[Dict[str, Any]],
) -> list[str]:
    out: list[str] = []
    dup: set[str] = set()

    def add(u: str, *, allow_noise: bool = False) -> None:
        s = _img_url_canonical(str(u or ""))
        if not s or s in dup:
            return
        if not allow_noise and _is_likely_noise_image_url(s):
            return
        if not s.startswith("http"):
            return
        if s:
            dup.add(s)
            out.append(s)

    # Покрываем кейс, когда detail пустой/урезан, а в листинге есть только "грязная" обложка.
    add(row_img, allow_noise=True)
    if not detail or not isinstance(detail, dict):
        return out
    for key in (
        "head_images",
        "image_list",
        "images",
        "sku_image_list",
        "car_image_list",
        "photo_list",
        "image_url_list",
        "car_image_info_list",
        "appearance_image_list",
        "interior_image_list",
        "space_image_list",
        "official_photo_list",
        "sku_car_image_list",
    ):
        raw = detail.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, str):
                add(item)
            elif isinstance(item, dict):
                u = _first_nonempty_str(
                    item.get("url"),
                    item.get("image"),
                    item.get("image_url"),
                    item.get("pic_url"),
                    item.get("picUrl"),
                    item.get("big_url"),
                    item.get("bigUrl"),
                    item.get("thumb_url"),
                    item.get("thumbUrl"),
                    item.get("cover_url"),
                    item.get("coverUrl"),
                )
                add(u)
    # Глубокий обход нужен как fallback, но он часто приносит нерелевантные маркетинговые ассеты.
    # Поэтому включаем его только при бедной галерее.
    if len(out) < 4:
        for u in _deep_collect_image_urls(detail, max_urls=40):
            add(u)
    return out


def dongchedi_spec_car_id(detail: Optional[Dict[str, Any]]) -> Optional[str]:
    """ID комплектации для /auto/params-carIds-{id} — из карточки б/у."""
    if not detail or not isinstance(detail, dict):
        return None
    hint = detail.get("_spec_car_id_hint")
    if hint is not None and str(hint).strip().isdigit():
        return str(hint).strip()
    for key in ("car_info", "car_config_overview"):
        block = detail.get(key)
        if isinstance(block, dict):
            cid = block.get("car_id")
            if cid is not None and str(cid).strip():
                return str(cid).strip()
    # Fallback: в некоторых версиях payload car_id лежит глубже.
    def walk(o: Any, depth: int = 0) -> Optional[str]:
        if depth > 10 or o is None:
            return None
        if isinstance(o, dict):
            cid = o.get("car_id")
            if cid is not None and str(cid).strip().isdigit():
                s = str(cid).strip()
                if 3 <= len(s) <= 9:
                    return s
            for v in o.values():
                got = walk(v, depth + 1)
                if got:
                    return got
        elif isinstance(o, list):
            for it in o[:100]:
                got = walk(it, depth + 1)
                if got:
                    return got
        return None
    return walk(detail)


def _params_info_cell_value(info: Any, item_key: str) -> str:
    if not isinstance(info, dict):
        return ""
    cell = info.get(item_key)
    if isinstance(cell, dict):
        return str(cell.get("value") or "").strip()
    return str(cell or "").strip()


def _pick_params_car_info(params_raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ci_top = params_raw.get("car_info")
    if isinstance(ci_top, dict):
        return ci_top
    if isinstance(ci_top, list):
        # На части страниц car_info — список комплектаций; берём первую валидную.
        for item in ci_top:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("info"), dict) or item.get("car_id") is not None:
                return item
        for item in ci_top:
            if isinstance(item, dict):
                return item
    return None


def _apply_params_raw_to_data(
    data: Dict[str, Any],
    params_raw: Optional[Dict[str, Any]],
    *,
    cny_to_rub: float,
) -> None:
    """Данные с страницы параметров (МСРП нового, год модели, краткая комплектация)."""
    if not params_raw or not isinstance(params_raw, dict):
        return
    try:
        # Полный слепок параметров модели с страницы params-carIds-*.
        # Нужен как source-of-truth, чтобы не терять поля при изменениях структуры.
        data["dongchedi_params_raw"] = json.dumps(params_raw, ensure_ascii=False)
    except Exception:
        pass
    ci_top = _pick_params_car_info(params_raw)
    if not isinstance(ci_top, dict):
        return
    car_id = str(ci_top.get("car_id") or "").strip()
    if car_id:
        data["dongchedi_specs_car_id"] = car_id
        data["dongchedi_specs_url"] = f"https://www.dongchedi.com/auto/params-carIds-{car_id}"

    cn = _first_nonempty_str(
        ci_top.get("car_name"),
        ci_top.get("trim_name"),
        ci_top.get("grade_name"),
        ci_top.get("version_name"),
        ci_top.get("sub_name"),
        ci_top.get("name"),
    )
    if cn:
        data["configuration"] = cn
        data["gradeName"] = cn
        g0, t0 = _split_generation_and_trim(cn)
        if g0:
            data["generation"] = g0
        if t0:
            data["trim_name"] = t0

    cy = ci_top.get("car_year")
    if isinstance(cy, str) and cy.isdigit() and len(cy) == 4:
        data["dongchedi_model_year"] = cy
    elif isinstance(cy, int) and 1990 <= cy <= 2035:
        data["dongchedi_model_year"] = str(cy)

    op = _first_nonempty_str(ci_top.get("official_price"), ci_top.get("dealer_price"))
    msrp = _parse_wan_price_text(op)
    if msrp is not None and msrp > 0:
        data["dongchedi_msrp_cny"] = round(msrp, 2)
        data["dongchedi_msrp_rub"] = round(float(msrp) * float(cny_to_rub))

    info = ci_top.get("info")
    mt = _params_info_cell_value(info, "market_time")
    if mt:
        data["dongchedi_market_time"] = mt

    if isinstance(info, dict):
        engine_desc = _params_info_cell_value(info, "engine_description")
        if engine_desc:
            data["dongchedi_engine_description"] = engine_desc
            if not data.get("dongchedi_displacement_label"):
                m = _DISP_LABEL_RE.search(engine_desc.upper())
                if m:
                    data["dongchedi_displacement_label"] = m.group(1) + ("T" if "T" in m.group(0).upper() else "L")
        gbx = _params_info_cell_value(info, "gearbox_description")
        if gbx:
            data["transmission_type"] = gbx
            data["dongchedi_gearbox_description"] = gbx
        body = _first_nonempty_str(
            _params_info_cell_value(info, "body_struct"),
            _params_info_cell_value(info, "car_body_struct"),
        )
        if body:
            data["body_type"] = body
        fuel = _first_nonempty_str(
            _params_info_cell_value(info, "fuel_form"),
            _params_info_cell_value(info, "fuel_label"),
        )
        if fuel and not data.get("engine_type"):
            data["engine_type"] = fuel
        power_text = _first_nonempty_str(
            _params_info_cell_value(info, "max_power"),
            _params_info_cell_value(info, "energy_elect_max_power"),
            _params_info_cell_value(info, "engine_max_power"),
        )
        kw = _parse_power_kw_text(power_text)
        if kw is not None:
            data["power_kw"] = kw
        hp_text = _first_nonempty_str(
            power_text,
            _params_info_cell_value(info, "engine_max_horsepower"),
        )
        hp = _parse_horsepower_ma(hp_text)
        if hp is not None and not data.get("hp"):
            data["hp"] = hp
        torque_text = _first_nonempty_str(
            _params_info_cell_value(info, "max_torque"),
            _params_info_cell_value(info, "energy_elect_max_torque"),
            _params_info_cell_value(info, "engine_max_torque"),
        )
        nm = _parse_torque_nm_text(torque_text)
        if nm is not None:
            data["torque_nm"] = nm

    highlights: list[Dict[str, str]] = []
    for key, label in (
        ("length", "Длина (мм)"),
        ("width", "Ширина (мм)"),
        ("height", "Высота (мм)"),
        ("wheelbase", "Колёсная база (мм)"),
        ("engine_model", "Двигатель (модель)"),
        ("engine_description", "Двигатель"),
        ("gearbox_description", "Коробка"),
        ("driver_form", "Привод"),
        ("fuel_label", "Топливо"),
        ("environmental_standards", "Экостандарт"),
        ("fuel_comprehensive", "Расход NEDC (л/100км)"),
        ("body_struct", "Кузов"),
        ("max_speed", "Vmax (км/ч)"),
    ):
        v = _params_info_cell_value(info, key)
        if v and len(v) < 200:
            highlights.append({"key": key, "label": label, "value": v})
    if highlights:
        data["dongchedi_specs_highlights"] = json.dumps(highlights, ensure_ascii=False)


def _china_static_maps() -> Dict[str, Dict[str, Dict[str, str]]]:
    global _CHINA_STATIC_MAPS
    if _CHINA_STATIC_MAPS is not None:
        return _CHINA_STATIC_MAPS
    path = Path(__file__).resolve().parents[2] / "data" / "china_static_terms.json"
    if not path.is_file():
        _CHINA_STATIC_MAPS = {"en": {}, "ru": {}}
        return _CHINA_STATIC_MAPS
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _CHINA_STATIC_MAPS = {"en": {}, "ru": {}}
        return _CHINA_STATIC_MAPS
    _CHINA_STATIC_MAPS = {
        "en": raw.get("en") if isinstance(raw, dict) and isinstance(raw.get("en"), dict) else {},
        "ru": raw.get("ru") if isinstance(raw, dict) and isinstance(raw.get("ru"), dict) else {},
    }
    return _CHINA_STATIC_MAPS


def _apply_china_static_mapping(data: Dict[str, Any]) -> None:
    maps = _china_static_maps()

    for field in ("mark", "model", "generation", "configuration", "gradeName"):
        src = str(data.get(field) or "").strip()
        if not src:
            continue
        data.setdefault(f"{field}_original", src)
        en = (maps.get("en", {}).get(field, {}) or {}).get(src)
        if not en and field in ("configuration", "gradeName"):
            en = (maps.get("en", {}).get("trim_name", {}) or {}).get(src)
        if not en:
            domain = "trim_name" if field in ("configuration", "gradeName") else field
            en = facet_canonical_english(src, domain)
        if en:
            data[field] = en
            data[f"{field}_en"] = en

    for field in ("engine_type", "transmission_type", "body_type", "color", "drive_type", "prep_drive_type"):
        src = str(data.get(field) or "").strip()
        if not src:
            continue
        data.setdefault(f"{field}_original", src)
        ru = (maps.get("ru", {}).get(field, {}) or {}).get(src)
        if ru:
            data[field] = ru
            data[f"{field}_ru"] = ru

    title = " ".join(
        x
        for x in (
            str(data.get("mark") or "").strip(),
            str(data.get("model") or "").strip(),
            str(data.get("generation") or "").strip(),
        )
        if x
    ).strip()
    if title:
        data["title_en"] = title


def sku_row_to_payload(
    row: Dict[str, Any],
    *,
    detail: Optional[Dict[str, Any]] = None,
    cny_to_rub: float = 13.0,
) -> Dict[str, Any]:
    """
    row — элемент search_sh_sku_info_list.
    detail — объект skuDetail из __NEXT_DATA__ (опционально, для цены в CNY).
    Опционально detail['_params_raw'] — pageProps.rawData со страницы params-carIds.
    """
    sku_id = row.get("sku_id")
    if sku_id is None:
        return {"data": {}}
    sid = str(sku_id).strip()
    if not sid:
        return {"data": {}}

    params_raw: Optional[Dict[str, Any]] = None
    spec_car_id_hint: Optional[str] = None
    if detail and isinstance(detail, dict):
        spec_car_id_hint = dongchedi_spec_car_id(detail)
        if isinstance(detail.get("_params_raw"), dict):
            detail = dict(detail)
            params_raw = detail.pop("_params_raw", None)

    title = str(row.get("title") or "").strip()
    brand_name = str(row.get("brand_name") or "").strip()
    series_name = str(row.get("series_name") or "").strip()
    mark = brand_name or "中国二手车"
    model = series_name or title or f"{series_name} {row.get('car_name') or ''}".strip() or f"Dongchedi #{sid}"

    ci: Dict[str, Any] = {}
    if detail and isinstance(detail.get("car_info"), dict):
        ci = detail["car_info"]

    cy = row.get("car_year")
    year = str(int(cy)) if isinstance(cy, int) else (str(cy).strip() if cy not in (None, "") else "")
    cy_ci = ci.get("year") if ci else None
    if isinstance(cy_ci, int) and 1990 <= cy_ci <= 2035:
        year = str(cy_ci)
    year_month = ""
    if year and len(year) == 4 and year.isdigit():
        year_month = f"{year}01"

    km_age = _km_from_mileage_str(str(row.get("car_mileage") or ""))
    if km_age is None and ci:
        km_age = _km_from_car_info_mileage_value(ci.get("mileage"))

    img = str(row.get("image") or "").strip()
    urls = _image_urls_from_row_and_detail(img, detail)
    images_json = json.dumps(urls, ensure_ascii=False) if urls else None

    price_cny: Optional[float] = None
    if detail:
        price_cny = _fen_to_cny(detail.get("source_sh_price"))
        if price_cny is None:
            price_cny = _parse_wan_price_text(str(detail.get("include_tax_price") or ""))
        if price_cny is None:
            price_cny = _parse_wan_price_text(str(detail.get("offical_price") or ""))

    my_price: Optional[float] = None
    if price_cny is not None and price_cny > 0:
        my_price = round(float(price_cny) * float(cny_to_rub))

    url = f"https://www.dongchedi.com/usedcar/{sid}"

    data: Dict[str, Any] = {
        "source": "dongchedi",
        "dongchedi_sku_id": sid,
        "inner_id": sid,
        "url": url,
        "dongchedi_usedcar_url": url,
        "mark": mark,
        "model": model,
        "offer_created": _utc_date_tag(),
        "created_at": _utc_date_tag(),
    }
    if year:
        data["year"] = year
    if year_month:
        data["yearMonth"] = year_month
    if my_price is not None:
        data["my_price"] = my_price
    if price_cny is not None and price_cny > 0:
        data["price_cny"] = price_cny
    if images_json:
        data["images"] = images_json
    if row.get("series_id") is not None:
        data["dongchedi_series_id"] = row.get("series_id")
    if row.get("brand_id") is not None:
        data["dongchedi_brand_id"] = row.get("brand_id")
    if series_name:
        data["dongchedi_series_name"] = series_name

    if ci:
        col = _first_nonempty_str(
            ci.get("body_color"),
            ci.get("color"),
            ci.get("car_color"),
            ci.get("exterior_color_name"),
            ci.get("exterior_color"),
        )
        if col:
            data["color"] = col
        trans = _first_nonempty_str(
            ci.get("transmission"),
            ci.get("gear_type"),
            ci.get("gearbox"),
            ci.get("gearbox_type"),
        )
        if trans:
            data["transmission_type"] = trans
        fuel = _first_nonempty_str(
            ci.get("fuel_type"),
            ci.get("fuel"),
            ci.get("energy_type"),
            ci.get("engine_type"),
        )
        if fuel:
            data["engine_type"] = fuel
        disp = _first_nonempty_str(ci.get("displacement"), ci.get("liter"))
        if disp:
            data["displacement"] = disp
        vin = _first_nonempty_str(ci.get("vin"))
        if vin:
            data["vin"] = vin
        city = _first_nonempty_str(ci.get("city_name"), ci.get("city"))
        if city:
            data["city"] = city

    row_city = _first_nonempty_str(row.get("car_source_city_name"))
    if row_city:
        data.setdefault("city", row_city)
    try:
        tc = row.get("transfer_cnt")
        if tc is not None and str(tc).strip() != "":
            data["transfer_count"] = int(tc)
    except (TypeError, ValueError):
        pass

    car_name_row = _first_nonempty_str(row.get("car_name"))
    if not data.get("generation"):
        g1, t1 = _split_generation_and_trim(car_name_row or title)
        if g1:
            data["generation"] = g1
        if t1 and not data.get("trim_name"):
            data["trim_name"] = t1
    if car_name_row:
        data.setdefault("configuration", car_name_row)
        data.setdefault("gradeName", car_name_row)
    elif title:
        data.setdefault("configuration", title)
        data.setdefault("gradeName", title)

    params = _param_pairs_from_detail(detail)
    if params:
        pv = params.get("车源地") or params.get("上牌地")
        if pv:
            data["city"] = pv
        pv = params.get("过户次数")
        if pv:
            pt = _parse_transfer_times(pv)
            if pt is not None:
                data["transfer_count"] = pt
        pv = params.get("上牌时间")
        if pv:
            y_reg, ym_reg = _parse_register_year_month(pv)
            if y_reg:
                data["year"] = y_reg
            if ym_reg:
                data["yearMonth"] = ym_reg
        pv = params.get("排量")
        if pv:
            cc = _displacement_cc_from_label(pv)
            if cc:
                data["displacement"] = cc
            elif not data.get("displacement"):
                data["dongchedi_displacement_label"] = str(pv).strip()
        pv = params.get("变速箱")
        if pv and not data.get("transmission_type"):
            data["transmission_type"] = str(pv).strip()
        pv = params.get("车身颜色")
        if pv:
            data["color"] = str(pv).strip()
        pv = params.get("内饰颜色")
        if pv:
            data["interior_color"] = str(pv).strip()
        if km_age is None:
            km2 = _km_from_param_pairs(params)
            if km2 is not None:
                km_age = km2

    itext = _first_nonempty_str((detail or {}).get("important_text")) if detail else ""
    if itext:
        data["dongchedi_summary"] = itext
    options = _highlight_options_from_detail(detail)
    if options:
        data["dongchedi_recommended_options"] = json.dumps(options, ensure_ascii=False)
    if km_age is None and itext:
        km_age = _km_from_mileage_str(itext)
    if km_age is None:
        km_age = _km_from_detail_known_strings(detail)
    if km_age is None and detail:
        km_age = _km_walk_detail_for_mileage(detail)
    if km_age is None and detail and isinstance(detail.get("_mileage_hint_km"), (int, float)):
        hint = int(detail["_mileage_hint_km"])
        if 300 <= hint <= 2_000_000:
            km_age = hint

    cc_over = (detail or {}).get("car_config_overview") if detail else None
    if isinstance(cc_over, dict):
        cn = _first_nonempty_str(cc_over.get("car_name"))
        if cn:
            data["configuration"] = cn
            data["gradeName"] = cn
        man = cc_over.get("manipulation")
        if isinstance(man, dict):
            df = _first_nonempty_str(man.get("driver_form"))
            if df:
                data["drive_type"] = df
        powd = cc_over.get("power")
        if isinstance(powd, dict):
            hpv = _parse_horsepower_ma(powd.get("horsepower"))
            if hpv is not None:
                data["hp"] = hpv
            if not data.get("engine_type"):
                fu = _first_nonempty_str(powd.get("fuel_form"))
                if fu:
                    data["engine_type"] = fu
            if not data.get("transmission_type"):
                gbd = _first_nonempty_str(powd.get("gearbox_description"))
                if gbd:
                    data["transmission_type"] = gbd
            if not data.get("displacement") and not data.get("dongchedi_displacement_label"):
                cap = _first_nonempty_str(powd.get("capacity"))
                if cap:
                    cc2 = _displacement_cc_from_label(cap)
                    if cc2:
                        data["displacement"] = cc2
                    else:
                        data["dongchedi_displacement_label"] = cap

    if km_age is not None:
        data["km_age"] = km_age

    _apply_params_raw_to_data(data, params_raw, cny_to_rub=cny_to_rub)
    if spec_car_id_hint and not data.get("dongchedi_specs_url"):
        data["dongchedi_specs_car_id"] = spec_car_id_hint
        data["dongchedi_specs_url"] = f"https://www.dongchedi.com/auto/params-carIds-{spec_car_id_hint}"
    _apply_china_static_mapping(data)

    return {"data": data}


def row_matches_filters(
    row: Dict[str, Any],
    *,
    series_id: Optional[int] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    price_min_cny: Optional[float] = None,
    price_max_cny: Optional[float] = None,
    price_cny: Optional[float] = None,
) -> bool:
    if series_id is not None:
        try:
            if int(row.get("series_id") or 0) != int(series_id):
                return False
        except (TypeError, ValueError):
            return False
    cy = row.get("car_year")
    y: Optional[int] = None
    if isinstance(cy, int):
        y = cy
    elif cy is not None and str(cy).isdigit():
        y = int(str(cy))
    if year_min is not None and y is not None and y < year_min:
        return False
    if year_max is not None and y is not None and y > year_max:
        return False
    if price_cny is not None and price_cny > 0:
        if price_min_cny is not None and price_cny < price_min_cny:
            return False
        if price_max_cny is not None and price_cny > price_max_cny:
            return False
    return True
