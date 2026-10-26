"""Публикация выгодных лотов в Telegram-канал (Article / Rich Message + карусель)."""
from __future__ import annotations

import html
import json
import logging
import re
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from encar_image_order import _sort_encar_image_url_list, _sort_h_images_list_entries
from fastapi_app.config import Settings
from fastapi_app.encar_option_ru import encar_option_ru, sanitize_trim_name, translate_ko_option_label

_log = logging.getLogger(__name__)

_MAX_PHOTOS = 10
_MAX_RICH_CHARS = 32_000
_ALBUM_CAPTION = 1024
_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_MARKET_HEADING = {
    "korea": "🇰🇷 Корея",
    "china": "🇨🇳 Китай",
    "usa": "🇺🇸 США",
    "japan": "🇯🇵 Япония",
}
_SOURCE_MARKET = {
    "encar": "korea",
    "korea": "korea",
    "che168": "china",
    "china": "china",
    "autotrader": "usa",
    "usa": "usa",
    "ussai": "japan",
    "japan": "japan",
}


def channel_telegram_configured(settings: Settings) -> bool:
    if not settings.channel_telegram_enabled:
        return False
    token = channel_bot_token(settings)
    chat = (settings.channel_telegram_chat_id or "").strip()
    return bool(token and chat)


def channel_bot_token(settings: Settings) -> str:
    return (
        (settings.channel_telegram_bot_token or "").strip()
        or (settings.lead_telegram_bot_token or "").strip()
    )


def channel_public_origin(settings: Settings) -> str:
    raw = (settings.channel_telegram_site_url or "").strip() or (
        settings.auth_magic_link_base_url or ""
    ).strip()
    return (raw or "https://rideauto.ru").rstrip("/")


def source_to_market(source: Any, fallback: str = "korea") -> str:
    raw = str(source or "").strip().lower()
    if raw in _SOURCE_MARKET:
        return _SOURCE_MARKET[raw]
    if "che168" in raw or raw == "china":
        return "china"
    if "autotrader" in raw or raw in {"usa", "us"}:
        return "usa"
    if "ussai" in raw or "japan" in raw:
        return "japan"
    if "encar" in raw or raw in {"korea", "kr"}:
        return "korea"
    return fallback if fallback in _MARKET_HEADING else "korea"


def _as_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if isinstance(v, float) and not v.is_integer():
            s = str(v).strip()
            return s or None
        return str(int(v))
    s = str(v).strip()
    return s or None


def _pick_int(v: Any) -> Optional[int]:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v == v:
        return int(v)
    s = _as_str(v)
    if not s:
        return None
    m = re.search(r"\d+", s.replace(" ", "").replace("\u00a0", ""))
    if not m:
        return None
    try:
        return int(m.group(0))
    except ValueError:
        return None


def _format_rub(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", " ") + " руб."


def _format_km(v: Any) -> Optional[str]:
    n = _pick_int(v)
    if n is None or n < 0:
        return None
    return f"{n:,}".replace(",", " ") + " км"


def _liters(data: Dict[str, Any]) -> Optional[str]:
    label = _as_str(data.get("displacement_label")) or _as_str(data.get("displacement"))
    if label:
        m = re.search(r"(\d+(?:\.\d+)?)\s*l", label, re.I)
        if m:
            return f"{m.group(1)} л"
        cc_m = re.search(r"(\d{3,5})\s*cc", label, re.I)
        if cc_m:
            liters = int(cc_m.group(1)) / 1000
            if 0 < liters < 20:
                return f"{liters:.1f}".rstrip("0").rstrip(".") + " л"
    cc = _pick_int(data.get("displacement_cc"))
    if cc and cc > 0:
        liters = cc / 1000
        return f"{liters:.1f}".rstrip("0").rstrip(".") + " л"
    return None


def _has_turbo(data: Dict[str, Any], title: str) -> bool:
    for key in ("turbo", "is_turbo", "engine_turbo"):
        v = data.get(key)
        if v in (True, 1, "1", "true", "True"):
            return True
    blob = " ".join(
        x
        for x in (
            title,
            _as_str(data.get("generation")),
            _as_str(data.get("configuration")),
            _as_str(data.get("trim_name")),
            _as_str(data.get("displacement_label")),
            _as_str(data.get("displacement")),
        )
        if x
    )
    return bool(re.search(r"\b(turbo|турбо|tsi|tfsi|tgdi|gdi-t|1\.\d+t)\b", blob, re.I))


def _fuel(data: Dict[str, Any]) -> Optional[str]:
    raw = (
        _as_str(data.get("engine_type"))
        or _as_str(data.get("fuel_type"))
        or _as_str(data.get("fuel"))
    )
    if not raw:
        return None
    low = raw.lower()
    if "дизел" in low or "diesel" in low:
        return "дизель"
    if "гибрид" in low or "hybrid" in low:
        return "гибрид"
    if "электр" in low or "electric" in low or low in {"ev"}:
        return "электро"
    if "бенз" in low or "gasoline" in low or "petrol" in low:
        return "бензин"
    return raw.lower()


def _engine_line(data: Dict[str, Any], title: str) -> Optional[str]:
    liters = _liters(data)
    fuel = _fuel(data)
    parts = [p for p in (liters, fuel) if p]
    if not parts:
        return None
    line = ", ".join(parts)
    if _has_turbo(data, title):
        return f"{line} (турбированный)"
    return line


def _power_line(data: Dict[str, Any]) -> Optional[str]:
    hp = _pick_int(data.get("power_hp")) or _pick_int(data.get("power")) or _pick_int(data.get("hp"))
    if not hp or hp <= 0:
        return None
    kw = _pick_int(data.get("power_kw")) or int(round(hp * 0.7355))
    return f"{hp} л.с. ({kw} кВт)"


def _torque_line(data: Dict[str, Any]) -> Optional[str]:
    nm = _pick_int(data.get("torque_nm")) or _pick_int(data.get("max_torque_nm")) or _pick_int(
        data.get("torque")
    )
    if not nm or nm <= 0:
        return None
    return f"{nm} Н·м"


def _drive_line(data: Dict[str, Any]) -> Optional[str]:
    raw = (
        _as_str(data.get("drive_type_ru"))
        or _as_str(data.get("drive_type"))
        or _as_str(data.get("drivemode"))
        or _as_str(data.get("drivingmode"))
    )
    if not raw:
        return None
    low = raw.lower()
    up = raw.upper()
    if "перед" in low or re.search(r"\b(2WD|FWD|前驱)\b", up):
        return "передний — FWD (2WD)"
    if "зад" in low or re.search(r"\b(RWD|后驱)\b", up):
        return "задний — RWD"
    if "полн" in low or re.search(r"\b(4WD|AWD|四驱)\b", up):
        return "полный — AWD (4WD)"
    return raw


def _trans_line(data: Dict[str, Any]) -> Optional[str]:
    raw = (
        _as_str(data.get("transmission_type_ru"))
        or _as_str(data.get("transmission_type"))
        or _as_str(data.get("gearbox"))
        or _as_str(data.get("transmission"))
    )
    if not raw:
        return None
    low = raw.lower()
    if "автомат" in low or "акпп" in low or low in {"at", "automatic", "2"}:
        return "автоматическая"
    if "механ" in low or "мкпп" in low or low in {"mt", "manual", "1"}:
        return "механическая"
    if "вариатор" in low or "cvt" in low or low == "3":
        return "вариатор"
    if "робот" in low or "dct" in low or low in {"4", "5"}:
        return "роботизированная"
    return raw


def _release_date(data: Dict[str, Any]) -> Optional[str]:
    ym = data.get("yearMonth") or data.get("year_month") or data.get("yearname") or data.get("regdate")
    if isinstance(ym, int) and 199_001 <= ym <= 2_039_12:
        year, month = divmod(ym, 100)
        if 1 <= month <= 12:
            return f"{year}.{month:02d}"
    s = _as_str(ym)
    if s:
        m = re.match(r"^(\d{4})\.(\d{1,2})$", s)
        if m:
            return f"{m.group(1)}.{int(m.group(2)):02d}"
        m = re.match(r"^(\d{4})-(\d{2})", s)
        if m:
            return f"{m.group(1)}.{m.group(2)}"
        m = re.match(r"^(\d{4})(\d{2})", s.replace(" ", ""))
        if m and 1 <= int(m.group(2)) <= 12:
            return f"{m.group(1)}.{m.group(2)}"
    year = _pick_int(data.get("year"))
    return str(year) if year and 1980 <= year <= 2100 else None


def _trim_name(data: Dict[str, Any]) -> Optional[str]:
    for key in ("trim_name", "configuration", "gradeName", "trim"):
        s = _as_str(data.get(key))
        if not s or len(s) > 48:
            continue
        cleaned = sanitize_trim_name(s)
        if cleaned:
            return cleaned
    return None


def _parse_jsonish(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return v
    return v


_LATIN_EQUIP_OK = {
    "ABS", "TCS", "ESC", "USB", "AUX", "TPMS", "LDWS", "HUD", "EPB", "ECS", "CD",
}
_HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")


def _equipment_label_ok(s: str) -> bool:
    if not s or s.isdigit() or re.fullmatch(r"[\W_]+", s):
        return False
    if _HANGUL_RE.search(s):
        return False
    if _CYRILLIC_RE.search(s):
        return True
    if s.upper() in _LATIN_EQUIP_OK:
        return True
    return bool(re.search(r"[A-Za-z]", s)) and len(s) >= 2


def collect_equipment_labels(data: Dict[str, Any], *, limit: int = 40) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []

    def push(raw: Any) -> None:
        if len(out) >= limit:
            return
        s = _as_str(raw)
        if not s:
            return
        if _HANGUL_RE.search(s):
            s = translate_ko_option_label(s) or ""
        if not _equipment_label_ok(s):
            return
        if s in seen:
            return
        seen.add(s)
        out.append(s)

    for key in ("che168_recommended_options", "options_real", "che168_options_enriched"):
        parsed = _parse_jsonish(data.get(key))
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    push(item.get("name") or item.get("value") or item.get("title"))
                else:
                    push(item)
    hl = _parse_jsonish(data.get("high_light_config"))
    if isinstance(hl, list):
        for item in hl:
            if isinstance(item, dict):
                push(item.get("name") or item.get("title") or item.get("value"))
    opts = _parse_jsonish(data.get("options"))
    if isinstance(opts, dict):
        standard = opts.get("standard")
        if isinstance(standard, list):
            for code in standard:
                push(encar_option_ru(code))
    extra = data.get("extra") if isinstance(data.get("extra"), dict) else {}
    selling = extra.get("sellingpoint") if isinstance(extra, dict) else None
    if isinstance(selling, dict):
        photos = selling.get("choiceOptionPhotos")
        if isinstance(photos, list):
            for row in photos:
                if not isinstance(row, dict):
                    continue
                code = _as_str(row.get("partCode")) or ""
                if code.startswith("SPEC_"):
                    continue
                push(row.get("partName"))
    return out


def is_petrol_or_diesel(data: Dict[str, Any]) -> bool:
    """Автопост: только бензин/дизель, без гибрида, электро, LPG/LPI и водорода."""
    blob = " ".join(
        x
        for x in (
            _as_str(data.get("engine_type")),
            _as_str(data.get("engine_type_ru")),
            _as_str(data.get("engine_type_original")),
            _as_str(data.get("fuel_type")),
            _as_str(data.get("fuel")),
        )
        if x
    )
    if not blob:
        return False
    low = blob.lower()
    if any(tok in low for tok in ("гибрид", "hybrid", "phev", "hev", "하이브리드")):
        return False
    if "전기" in blob and ("가솔린" in blob or "디젤" in blob or "+" in blob):
        return False
    if any(tok in low for tok in ("lpg", "lpi", "метан", "водород", "hydrogen", "cng", "수소")):
        return False
    if any(tok in low for tok in ("электро", "electric", "전기")):
        return False
    return any(
        tok in low
        for tok in ("бенз", "gasoline", "petrol", "가솔린", "дизел", "diesel", "디젤")
    )


def has_turnkey_customs_price(data: Dict[str, Any], price_rub: Optional[float]) -> bool:
    if price_rub is None or price_rub <= 0:
        return False
    if data.get("price_on_request") in (True, "true", "True", 1, "1"):
        return False
    clean = data.get("pricing_clean") if isinstance(data.get("pricing_clean"), dict) else {}
    tier = _as_str(data.get("pricing_tier")) or _as_str(clean.get("pricing_tier"))
    customs = data.get("customs_included")
    if customs is None:
        customs = clean.get("customs_included")
    if tier == "full_customs" or customs in (True, "true", "True", 1, "1"):
        return True
    return False


def collect_photo_urls(data: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> List[str]:
    blob: Dict[str, Any] = {}
    if extra:
        blob.update(extra)
    blob.update(data)
    seen: set[str] = set()
    out: List[str] = []

    def add(url: Any) -> None:
        if not isinstance(url, str):
            return
        s = url.strip()
        if s.startswith("//"):
            s = "https:" + s
        if not re.match(r"^https?://", s, re.I):
            return
        low = s.lower()
        if any(x in low for x in ("watermark", "/logo", "icon_", "banner", "poster")):
            return
        key = s.split("?")[0].lower()
        if key in seen:
            return
        seen.add(key)
        out.append(s.replace("http://", "https://"))

    for field in (
        "cover",
        "cover_image",
        "main_image",
        "image",
        "images",
        "h_images",
        "photos",
    ):
        parsed = _parse_jsonish(blob.get(field))
        if isinstance(parsed, str):
            add(parsed)
            continue
        if not isinstance(parsed, list):
            continue
        for item in parsed:
            if isinstance(item, str):
                add(item)
                continue
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            if isinstance(path, str) and path.startswith("/"):
                add(
                    "https://ci.encar.com/carpicture"
                    + path
                    + "?impolicy=heightRate&rh=696&cw=1160&ch=696&cg=Center"
                )
            for k in ("url", "imageUrl", "src", "image", "pic_url", "big_url", "cover_url"):
                add(item.get(k))
    market = source_to_market(blob.get("source"))
    if market == "korea" or any("encar.com" in u for u in out):
        hi = _parse_jsonish(blob.get("h_images"))
        if isinstance(hi, list):
            ordered_hi = _sort_h_images_list_entries([x for x in hi if isinstance(x, dict)])
            front_first: List[str] = []
            seen_hi: set[str] = set()
            for item in ordered_hi:
                path = item.get("path")
                if not isinstance(path, str) or not path.startswith("/"):
                    continue
                url = (
                    "https://ci.encar.com/carpicture"
                    + path
                    + "?impolicy=heightRate&rh=696&cw=1160&ch=696&cg=Center"
                )
                key = url.split("?")[0].lower()
                if key in seen_hi:
                    continue
                seen_hi.add(key)
                front_first.append(url)
            rest = [u for u in out if u.split("?")[0].lower() not in seen_hi]
            return (front_first + rest)[: _MAX_PHOTOS * 3]
        return _sort_encar_image_url_list(out)
    if market == "china":
        listing_ids = [
            _as_str(blob.get(k))
            for k in ("inner_id", "infoid", "infoId", "carid", "carId", "id")
            if _as_str(blob.get(k))
        ]
        filtered = [u for u in out if not _is_foreign_china_photo(u, listing_ids)]
        return filtered or out
    return out


def _is_foreign_china_photo(url: str, listing_ids: Sequence[str]) -> bool:
    low = url.lower()
    if "encar.com" in low:
        return True
    if "autoimg.cn" in low and "2sc" not in low:
        return True
    if any(tok in low for tok in ("/seriespic", "/modelpic", "factorypic", "/specimg")):
        return True
    digits = [re.sub(r"\D", "", x) for x in listing_ids if re.sub(r"\D", "", x)]
    if not digits:
        return False
    for m in re.finditer(r"(?:infoid|info_id|carid|car_id)=(\d{5,})", low):
        other = m.group(1)
        if not any(other == d or d.endswith(other) or other.endswith(d) for d in digits):
            return True
    return False


def build_car_title(*, mark: Any, model: Any, generation: Any, fallback: str = "") -> str:
    parts: List[str] = []
    for raw in (mark, model):
        s = _as_str(raw)
        if s:
            parts.append(s)
    gen = _as_str(generation)
    if gen and len(gen) <= 40 and gen.lower() not in {p.lower() for p in parts}:
        if not any(gen.lower() in p.lower() for p in parts):
            parts.append(gen)
    title = " ".join(parts).strip()
    return title or fallback or "Автомобиль"


def _publication_label(published_at: Any) -> str:
    if isinstance(published_at, datetime):
        return published_at.strftime("%d.%m.%Y")
    if isinstance(published_at, date):
        return published_at.strftime("%d.%m.%Y")
    s = _as_str(published_at)
    if s:
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
        if m:
            return f"{m.group(3)}.{m.group(2)}.{m.group(1)}"
    return datetime.now().strftime("%d.%m.%Y")


_ARTICLE_GAP = "<br><br>"
# После <blockquote> соседний <p> липнет; отдельный nbsp-абзац даёт тот же зазор, что <br><br> внутри текста.
_QUOTE_TAIL = "<p>\u00a0</p>"


def _hard_lines(lines: Sequence[str]) -> str:
    """Одиночный \\n в Rich Markdown схлопывается в пробел — фиксируем через <br>."""
    clean = [ln.rstrip() for ln in lines if ln.strip()]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    return "<br>\n".join(clean)


def _article_bold(text: str) -> str:
    return f"<b>{text}</b>"


def _article_paragraph(chunks: Sequence[str]) -> str:
    parts = [c for c in chunks if c]
    if not parts:
        return ""
    return f"<p>{_ARTICLE_GAP.join(parts)}</p>"


def build_channel_caption(
    *,
    title: str,
    data: Dict[str, Any],
    price_rub: Optional[float],
    market: str = "korea",
    published_at: Any = None,
    buy_url: str = "https://rideauto.ru/buy",
    manager_url: str = "https://t.me/nikits15",
    equipment: Optional[Sequence[str]] = None,
) -> str:
    heading = _MARKET_HEADING.get(source_to_market(data.get("source"), market), "🇰🇷 Корея")
    sections: List[str] = [f"**{heading}**", f"**🏎 {title}**"]
    specs: List[Tuple[str, Optional[str]]] = [
        ("Двигатель", _engine_line(data, title)),
        ("Мощность", _power_line(data)),
        ("Крутящий момент", _torque_line(data)),
        ("Привод", _drive_line(data)),
        ("Трансмиссия", _trans_line(data)),
        ("Дата выпуска", _release_date(data)),
        ("Пробег", _format_km(data.get("km_age") if data.get("km_age") is not None else data.get("mileage_km"))),
    ]
    spec_lines = [f"• {label}: {value}" for label, value in specs if value]
    if spec_lines:
        sections.append(_hard_lines(spec_lines))
    trim = _trim_name(data)
    eq = list(equipment) if equipment is not None else collect_equipment_labels(data)
    if trim or eq:
        sections.append(f"**Комплектация {trim}:**" if trim else "**Комплектация:**")
        if eq:
            sections.append(_hard_lines([f"> {item}" for item in eq]))
    if price_rub is not None and price_rub > 0:
        sections.append(f"**💳 Цена во Владивостоке под ключ: {_format_rub(price_rub)}**")
    else:
        sections.append("**💳 Цена во Владивостоке под ключ: по запросу**")
    sections.append(f"Цена является актуальной на момент публикации — {_publication_label(published_at)}")
    sections.append(
        f"[⬇️ Оставить заявку]({buy_url}) | [📞 Связаться]({manager_url})"
    )
    return "\n\n".join(sections)[:_MAX_RICH_CHARS]


def build_channel_html(
    *,
    title: str,
    data: Dict[str, Any],
    price_rub: Optional[float],
    market: str = "korea",
    published_at: Any = None,
    buy_url: str = "https://rideauto.ru/buy",
    manager_url: str = "https://t.me/nikits15",
    equipment: Optional[Sequence[str]] = None,
) -> str:
    """HTML Article: абзацы, список характеристик и quote комплектации."""

    def esc(v: Any) -> str:
        return html.escape(str(v), quote=False)

    heading = _MARKET_HEADING.get(source_to_market(data.get("source"), market), "🇰🇷 Корея")
    specs: List[Tuple[str, Optional[str]]] = [
        ("Двигатель", _engine_line(data, title)),
        ("Мощность", _power_line(data)),
        ("Крутящий момент", _torque_line(data)),
        ("Привод", _drive_line(data)),
        ("Трансмиссия", _trans_line(data)),
        ("Дата выпуска", _release_date(data)),
        ("Пробег", _format_km(data.get("km_age") if data.get("km_age") is not None else data.get("mileage_km"))),
    ]
    spec_html = "<br>".join(f"• {esc(label)}: {esc(value)}" for label, value in specs if value)
    trim = _trim_name(data)
    eq = list(equipment) if equipment is not None else collect_equipment_labels(data)
    top: List[str] = [_article_bold(esc(heading)), _article_bold(f"🏎 {esc(title)}")]
    if spec_html:
        top.append(spec_html)
    if trim or eq:
        top.append(_article_bold(f"Комплектация {esc(trim)}:" if trim else "Комплектация:"))
    quote = ""
    if eq:
        quoted = "".join(f"<p>&gt; {esc(item)}</p>" for item in eq)
        quote = f"<blockquote>{quoted}</blockquote>{_QUOTE_TAIL}"
    if price_rub is not None and price_rub > 0:
        price_line = _article_bold(f"💳 Цена во Владивостоке под ключ: {esc(_format_rub(price_rub))}")
    else:
        price_line = _article_bold("💳 Цена во Владивостоке под ключ: по запросу")
    bottom = [
        price_line,
        f"Цена является актуальной на момент публикации — {esc(_publication_label(published_at))}",
        (
            f'<a href="{html.escape(buy_url, quote=True)}">⬇️ Оставить заявку</a>'
            f' | <a href="{html.escape(manager_url, quote=True)}">📞 Связаться</a>'
        ),
    ]
    return f"{_article_paragraph(top)}{quote}{_article_paragraph(bottom)}"[:_MAX_RICH_CHARS]


def _inline_md_to_html(s: str) -> str:
    out: List[str] = []
    pos = 0
    for m in _MD_LINK_RE.finditer(s):
        out.append(html.escape(s[pos : m.start()]))
        out.append(f'<a href="{html.escape(m.group(2), quote=True)}">{html.escape(m.group(1))}</a>')
        pos = m.end()
    out.append(html.escape(s[pos:]))
    return "".join(out)


def caption_to_html(text: str) -> str:
    """Перенос markdown-описания карточки в HTML Article (bold + quote, без h1–h6)."""
    out: List[str] = []
    buf: List[str] = []

    def flush() -> None:
        if buf:
            out.append(_article_paragraph(buf))
            buf.clear()

    for block in re.split(r"\n{2,}", (text or "").strip()):
        lines = [ln.rstrip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        if all(ln.lstrip().startswith(">") for ln in lines):
            flush()
            quoted = "".join(
                f"<p>&gt; {html.escape(ln.lstrip()[1:].strip())}</p>" for ln in lines
            )
            out.append(f"<blockquote>{quoted}</blockquote>{_QUOTE_TAIL}")
            continue
        raw = lines[0]
        plain = raw.strip().lstrip("*").rstrip("*").strip()
        is_heading = len(lines) == 1 and (
            plain.startswith("🇰🇷")
            or plain.startswith("🏎")
            or plain.startswith("Комплектация")
            or plain.startswith("💳")
        )
        if is_heading:
            buf.append(_article_bold(_inline_md_to_html(plain)))
            continue
        buf.append("<br>".join(_inline_md_to_html(ln) for ln in lines))
    flush()
    return "".join(out)[:_MAX_RICH_CHARS]


def score_channel_deal(
    *,
    source: str,
    price_rub: Optional[float],
    mileage_km: Optional[int],
    year: Optional[int],
    photo_count: int,
    damaged_parts: Optional[int] = None,
) -> float:
    score = 0.0
    src = (source or "").lower()
    if src in {"encar", "korea"}:
        score += 30
    elif src in {"che168", "china"}:
        score += 18
    score += min(20.0, float(photo_count) * 2)
    if year and year >= 2023:
        score += 12
    elif year and year >= 2020:
        score += 6
    if mileage_km is not None:
        if mileage_km < 40_000:
            score += 12
        elif mileage_km < 80_000:
            score += 6
        score -= mileage_km / 25_000
    if price_rub is not None:
        if 1_200_000 <= price_rub <= 3_200_000:
            score += 14
        elif 800_000 <= price_rub <= 4_500_000:
            score += 6
    if damaged_parts in (0, None):
        score += 8
    else:
        score -= min(20.0, float(damaged_parts) * 3)
    return score


def _tg_json(token: str, method: str, payload: Dict[str, Any], *, timeout: int = 45) -> Dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib_request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"telegram_http_{exc.code}: {err_body}") from exc
    data = json.loads(raw)
    if not data.get("ok"):
        raise RuntimeError(f"telegram_api_error: {data}")
    return data


def _rich_payload(
    chat_id: str,
    photo_urls: Sequence[str],
    *,
    html_body: Optional[str] = None,
    text: str = "",
) -> Dict[str, Any]:
    """Article: ровно одно из html / markdown / blocks. Карусель + тело — HTML (абзацы не схлопываются)."""
    imgs = "".join(f'<img src="{html.escape(u, quote=True)}"/>' for u in photo_urls[:_MAX_PHOTOS])
    if len(photo_urls) >= 2:
        media = f"<tg-slideshow>{imgs}</tg-slideshow>"
    else:
        media = imgs
    body = (html_body or "").strip() or f"<p>{html.escape(text).replace(chr(10), '<br>')}</p>"
    return {
        "chat_id": chat_id,
        "rich_message": {
            "html": f"{media}{body}",
        },
    }


def _extract_message_id(data: Dict[str, Any]) -> Optional[int]:
    result = data.get("result")
    if isinstance(result, dict):
        mid = result.get("message_id")
        return int(mid) if mid is not None else None
    if isinstance(result, list) and result:
        first = result[0]
        if isinstance(first, dict) and first.get("message_id") is not None:
            return int(first["message_id"])
    return None


def send_channel_article_sync(
    *,
    photo_urls: Sequence[str],
    text: str,
    settings: Settings,
    html_body: Optional[str] = None,
) -> Dict[str, Any]:
    token = channel_bot_token(settings)
    chat_id = (settings.channel_telegram_chat_id or "").strip()
    if not token or not chat_id:
        raise RuntimeError("telegram_channel_not_configured")
    urls = [u.strip() for u in photo_urls if isinstance(u, str) and u.strip()][:_MAX_PHOTOS]
    if not urls:
        raise RuntimeError("telegram_no_photos")
    body = text.strip()[:_MAX_RICH_CHARS]
    try:
        data = _tg_json(
            token,
            "sendRichMessage",
            _rich_payload(chat_id, urls, html_body=html_body, text=body),
        )
        return {"ok": True, "mode": "rich", "message_id": _extract_message_id(data)}
    except RuntimeError as exc:
        _log.warning("sendRichMessage failed, fallback album: %s", exc)
    media: List[Dict[str, Any]] = []
    short = body[:_ALBUM_CAPTION]
    for i, url in enumerate(urls):
        item: Dict[str, Any] = {"type": "photo", "media": url}
        if i == 0:
            item["caption"] = short
        media.append(item)
    album = _tg_json(token, "sendMediaGroup", {"chat_id": chat_id, "media": media})
    follow = None
    if len(body) > _ALBUM_CAPTION:
        follow = _tg_json(
            token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": body[:4000],
                "disable_web_page_preview": True,
            },
        )
    return {
        "ok": True,
        "mode": "album",
        "message_id": _extract_message_id(album) or ( _extract_message_id(follow) if follow else None),
    }


def public_proxy_photo_urls(origin: str, originals: Iterable[str]) -> List[str]:
    from fastapi_app.image_service import digest_for_url

    base = origin.rstrip("/")
    out: List[str] = []
    for src in originals:
        s = (src or "").strip()
        if not s:
            continue
        digest = digest_for_url(s)
        qs = urllib_parse.urlencode({"size": "medium", "src": s})
        out.append(f"{base}/api/images/{digest}?{qs}")
        if len(out) >= _MAX_PHOTOS:
            break
    return out
