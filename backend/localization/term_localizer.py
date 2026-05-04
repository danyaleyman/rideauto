from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import psycopg2


_KO_RE = re.compile(r"[\uac00-\ud7af]")
_ZH_RE = re.compile(r"[\u4e00-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")

_RU_TERM_MAP: Dict[str, str] = {
    "汽油": "Бензин",
    "柴油": "Дизель",
    "电动": "Электро",
    "插电式混合动力": "Подключаемый гибрид",
    "油电混动": "Гибрид",
    "自动": "Автомат",
    "手动": "Механика",
    "无级变速": "Вариатор",
    "双离合": "Робот",
    "前驱": "Передний",
    "后驱": "Задний",
    "全时四驱": "Полный привод",
    "适时四驱": "Полный привод",
    "分时四驱": "Полный привод",
    "白色": "Белый",
    "黑色": "Черный",
    "灰色": "Серый",
    "银色": "Серебристый",
    "红色": "Красный",
    "蓝色": "Синий",
    "绿色": "Зеленый",
    "棕色": "Коричневый",
    "黄色": "Желтый",
    "紫色": "Фиолетовый",
    "橙色": "Оранжевый",
}


def _as_text(v: object) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return s


def detect_lang(text: str) -> str:
    if not text:
        return "unknown"
    if _KO_RE.search(text):
        return "ko"
    if _ZH_RE.search(text):
        return "zh"
    return "other"


def _looks_english(text: str) -> bool:
    if not text:
        return False
    ascii_letters = sum(1 for ch in text if ("a" <= ch.lower() <= "z"))
    return ascii_letters >= max(3, len(text) // 2)


def _contains_latin(text: str) -> bool:
    return bool(_LATIN_RE.search(text or ""))


def _romanize_ko(text: str) -> str:
    try:
        from hangul_romanize import Transliter
        from hangul_romanize.rule import academic

        tr = Transliter(academic)
        out = tr.translit(text)
        return out.strip() if out else text
    except Exception:
        return text


def _romanize_zh(text: str) -> str:
    try:
        from pypinyin import lazy_pinyin

        parts = lazy_pinyin(text)
        out = " ".join(p for p in parts if p).strip()
        return out if out else text
    except Exception:
        return text


_KOREA_STATIC: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None
_CHINA_STATIC: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None
_KOREA_MARK_ALIASES: Optional[Dict[str, str]] = None
_KOREA_EN_DOMAIN_ALIAS_LOCK = threading.Lock()
_KOREA_EN_DOMAIN_ALIAS_CACHE: Dict[str, Dict[str, str]] = {}
_KOREA_EN_DOMAIN_NAMES = frozenset({"mark", "model", "generation", "configuration", "gradeName", "trim_name", "modelGroupName"})
_CHINA_EN_DOMAIN_ALIAS_LOCK = threading.Lock()
_CHINA_EN_DOMAIN_ALIAS_CACHE: Dict[str, Dict[str, str]] = {}
_CHINA_EN_DOMAIN_NAMES = frozenset({"mark", "model", "generation", "configuration", "gradeName", "trim_name", "modelGroupName"})
_KOREA_MARK_EXACT_OVERRIDES: Dict[str, str] = {
    "KG모빌리티(쌍용)": "KG Mobility (SsangYong)",
    "기아": "Kia",
    "닛산": "Nissan",
    "닷지": "Dodge",
    "도요타": "Toyota",
    "랜드로버": "Land Rover",
    "렉서스": "Lexus",
    "롤스로이스": "Rolls-Royce",
    "르노코리아(삼성)": "Renault Korea (Samsung)",
    "링컨": "Lincoln",
    "마세라티": "Maserati",
    "미니": "Mini",
    "미쯔비시": "Mitsubishi",
    "벤츠": "Mercedes-Benz",
    "벤틀리": "Bentley",
    "볼보": "Volvo",
    "쉐보레(GM대우)": "Chevrolet (GM Daewoo)",
    "스마트": "Smart",
    "스즈키": "Suzuki",
    "시트로엥/DS": "Citroën/DS",
    "아우디": "Audi",
    "재규어": "Jaguar",
    "제네시스": "Genesis",
    "지프": "Jeep",
    "캐딜락": "Cadillac",
    "테슬라": "Tesla",
    "페라리": "Ferrari",
    "포드": "Ford",
    "포르쉐": "Porsche",
    "폭스바겐": "Volkswagen",
    "폴스타": "Polestar",
    "푸조": "Peugeot",
    "현대": "Hyundai",
    "혼다": "Honda",
}
_KOREA_MARK_ALIAS_OVERRIDES: Dict[str, str] = {
    "a-udi": "Audi",
    "alpa lome-o": "Alfa Romeo",
    "aeseuteonmatin": "Aston Martin",
    "bencheu": "Mercedes-Benz",
    "benteulli": "Bentley",
    "bolbo": "Volvo",
    "do-yota": "Toyota",
    "dongpungsokon": "Dongfeng Sokon",
    "gi-a": "Kia",
    "gita jejosa": "Other Manufacturer",
    "hyeondae": "Hyundai",
    "inpiniti": "Infiniti",
    "jenesiseu": "Genesis",
    "jipeu": "Jeep",
    "laendeulobeo": "Land Rover",
    "leunokoli-a(samseong)": "Renault Korea (Samsung)",
    "lingkeon": "Lincoln",
    "maselati": "Maserati",
    "podeu": "Ford",
    "pogseubagen": "Volkswagen",
    "poleuswe": "Polestar",
    "polseuta": "Polestar",
    "teseulla": "Tesla",
}
_CHINA_MARK_EXACT_OVERRIDES: Dict[str, str] = {
    "方程豹": "Fangchengbao",
    "迈巴赫": "Maybach",
}
_CHINA_PINYIN_SUBSTRING_REPLACEMENTS: Dict[str, str] = {
    "bao ma": "BMW",
    "ben chi": "Mercedes-Benz",
    "da zhong": "Volkswagen",
    "ao di": "Audi",
    "bao shi jie": "Porsche",
    "ka di la ke": "Cadillac",
    "lu hu": "Land Rover",
    "jie bao": "Jaguar",
    "fu te": "Ford",
    "xue fu lan": "Chevrolet",
    "ying fei ni di": "Infiniti",
    "lei ke sa si": "Lexus",
    "ji li": "Geely",
    "chang an": "Changan",
    "hong qi": "Hongqi",
    "tan xian zhe": "Explorer",
    "rui jie": "Edge",
    "gao er fu": "Golf",
    "pu la duo": "Prado",
    "da qie nuo ji": "Grand Cherokee",
    "lan sheng ji guang": "Wrangler",
    "ke wo zi": "Cruze",
    "ke lu ze": "Cruze",
    "mai teng": "Magotan",
    "lan de ku lu ze": "Land Cruiser",
    "hang hai jia": "Navigator",
    "han lan da": "Highlander",
    "fu ke si": "Focus",
}
_CHINA_PINYIN_TOKEN_REPLACEMENTS: Dict[str, str] = {
    r"\bliang\s*qu\b": "2WD",
    r"\bsi\s*qu\b": "4WD",
    r"\bqian\s*qu\b": "FWD",
    r"\bhou\s*qu\b": "RWD",
    r"\bzeng\s*cheng\b": "EREV",
    r"\bchao\s*chang\s*xu\s*hang\b": "Long Range",
    r"\bchang\s*xu\s*hang\b": "Long Range",
    r"\bbiao\s*zhun\b": "Standard",
    r"\bhao\s*hua\b": "Luxury",
    r"\bqi\s*jian\b": "Flagship",
    r"\bzhi\s*xiang\b": "Zhixiang",
    r"\bzhi\s*tu\b": "Zhitu",
    r"\bzhi\s*zun\b": "Premium",
    r"\bjin\s*kou\b": "Import",
    r"\bgai\s*kuan\b": "Facelift",
}
_CHINA_TRIM_NOISE_TOKEN_RE = re.compile(
    r"\b("
    r"\d(?:\.\d)?t|"
    r"\d{2,4}t|"
    r"cvt|dct|amt|at|mt|"
    r"ecoboost|pro|plus|vi|v6|v8|"
    r"gw4[a-z0-9]+|"
    r"\d{4}"
    r")\b",
    re.IGNORECASE,
)


def _cleanup_china_en_text(text: str, *, domain: str) -> str:
    s = _as_text(text)
    if not s:
        return ""
    low = s.lower()
    for needle, repl in _CHINA_PINYIN_SUBSTRING_REPLACEMENTS.items():
        if needle in low:
            s = re.sub(re.escape(needle), repl, s, flags=re.IGNORECASE)
            low = s.lower()
    for patt, repl in _CHINA_PINYIN_TOKEN_REPLACEMENTS.items():
        s = re.sub(patt, repl, s, flags=re.IGNORECASE)
    s = re.sub(r"[()\[\]{}]+", " ", s)
    s = re.sub(r"[\u4e00-\u9fff\uac00-\ud7af]+", " ", s)
    s = " ".join(s.split())
    s = re.sub(r"^([A-Za-z0-9&\-]+)\s+\1\b", r"\1", s, flags=re.IGNORECASE).strip()
    if domain == "model":
        # У моделей обрезаем хвосты комплектаций/моторов.
        s = re.sub(r"\b20\d{2}\b.*$", "", s, flags=re.IGNORECASE).strip()
        s = re.sub(r"\b\d(?:\.\d)?T\b.*$", "", s, flags=re.IGNORECASE).strip()
        s = re.sub(r"\b(2WD|4WD|FWD|RWD|Long Range|EREV|Standard|Luxury|Flagship|Premium)\b.*$", "", s, flags=re.IGNORECASE).strip()
        s = re.sub(r"\s+", " ", s).strip(" -")
    if domain in {"generation", "trim_name", "configuration", "gradeName", "modelGroupName"}:
        s = re.sub(r"^\d+\s+", "", s).strip()
        s = re.sub(r"\s+", " ", s)
    return s.strip()


def is_china_trim_like_noise(text: object) -> bool:
    s = _cleanup_china_en_text(_as_text(text), domain="trim_name")
    if not s:
        return True
    letters = re.findall(r"[A-Za-z]+", s)
    if not letters:
        return True
    meaningful = [w for w in letters if len(w) >= 3 and w.lower() not in {"cvt", "dct", "amt", "at", "mt", "pro", "plus", "import"}]
    if meaningful:
        return False
    noisy = _CHINA_TRIM_NOISE_TOKEN_RE.sub(" ", s)
    noisy = re.sub(r"[\W_]+", " ", noisy).strip()
    return not bool(re.search(r"[A-Za-z]{3,}", noisy))


def _korea_static_maps() -> Dict[str, Dict[str, Dict[str, str]]]:
    """Статический словарь из data/korea_static_terms.json (не затирается nightly Encar)."""
    global _KOREA_STATIC
    if _KOREA_STATIC is not None:
        return _KOREA_STATIC
    path = Path(__file__).resolve().parents[2] / "data" / "korea_static_terms.json"
    if not path.is_file():
        _KOREA_STATIC = {"en": {}, "ru": {}}
        return _KOREA_STATIC
    raw = json.loads(path.read_text(encoding="utf-8"))
    _KOREA_STATIC = {
        "en": raw.get("en") or {},
        "ru": raw.get("ru") or {},
    }
    return _KOREA_STATIC


def _china_static_maps() -> Dict[str, Dict[str, Dict[str, str]]]:
    global _CHINA_STATIC
    if _CHINA_STATIC is not None:
        return _CHINA_STATIC
    path = Path(__file__).resolve().parents[2] / "data" / "china_static_terms.json"
    if not path.is_file():
        _CHINA_STATIC = {"en": {}, "ru": {}}
        return _CHINA_STATIC
    raw = json.loads(path.read_text(encoding="utf-8"))
    _CHINA_STATIC = {
        "en": raw.get("en") or {},
        "ru": raw.get("ru") or {},
    }
    return _CHINA_STATIC


def _lookup_korea_static(
    maps: Dict[str, Dict[str, Dict[str, str]]],
    text: str,
    target_lang: str,
    domain: str,
) -> Optional[str]:
    bucket = (maps.get(target_lang) or {}).get(domain) or {}
    return bucket.get(text)


def _lookup_china_static(
    maps: Dict[str, Dict[str, Dict[str, str]]],
    text: str,
    target_lang: str,
    domain: str,
) -> Optional[str]:
    bucket = (maps.get(target_lang) or {}).get(domain) or {}
    return bucket.get(text)


def _alias_key(text: str) -> str:
    return "".join(ch for ch in (text or "").lower() if ("a" <= ch <= "z") or ("0" <= ch <= "9"))


def _korea_mark_aliases() -> Dict[str, str]:
    global _KOREA_MARK_ALIASES
    if _KOREA_MARK_ALIASES is not None:
        return _KOREA_MARK_ALIASES
    aliases: Dict[str, str] = {}
    marks = (_korea_static_maps().get("en") or {}).get("mark") or {}
    for original, english in marks.items():
        eng = _as_text(english)
        if not eng:
            continue
        k_eng = _alias_key(eng)
        if k_eng:
            aliases[k_eng] = eng
        src = _as_text(original)
        if not src:
            continue
        if detect_lang(src) == "ko":
            rom = _romanize_ko(src)
            for cand in (rom, rom.replace("-", " "), rom.replace("-", ""), rom.replace(" ", "")):
                k = _alias_key(cand)
                if k and k not in aliases:
                    aliases[k] = eng
    for alias_raw, eng in _KOREA_MARK_ALIAS_OVERRIDES.items():
        k = _alias_key(alias_raw)
        if k:
            aliases[k] = eng
    _KOREA_MARK_ALIASES = aliases
    return _KOREA_MARK_ALIASES


def _korea_en_domain_alias_map_for(domain: str) -> Dict[str, str]:
    """
    Алиасы KO→EN для одного домена (ленивая сборка + lock: безопасно при параллельных /api/facets).
    Раньше строился весь dict сразу и блокировал ответ на минуты.
    """
    if domain not in _KOREA_EN_DOMAIN_NAMES:
        return {}
    with _KOREA_EN_DOMAIN_ALIAS_LOCK:
        cached = _KOREA_EN_DOMAIN_ALIAS_CACHE.get(domain)
        if cached is not None:
            return cached
        aliases: Dict[str, str] = {}
        bucket = ((_korea_static_maps().get("en") or {}).get(domain) or {})
        for original, english in bucket.items():
            eng = _as_text(english)
            if not eng:
                continue
            key_eng = _alias_key(eng)
            if key_eng:
                aliases[key_eng] = eng
            src = _as_text(original)
            if not src:
                continue
            if detect_lang(src) == "ko":
                rom = _romanize_ko(src)
                for cand in (rom, rom.replace("-", " "), rom.replace("-", ""), rom.replace(" ", "")):
                    k = _alias_key(cand)
                    if k and k not in aliases:
                        aliases[k] = eng
        _KOREA_EN_DOMAIN_ALIAS_CACHE[domain] = aliases
        return aliases


def _china_en_domain_alias_map_for(domain: str) -> Dict[str, str]:
    """
    Алиасы ZH/romanized-ZH → EN для China static map домена.
    Позволяет распознавать строки вроде 'bao ma', 'ben chi', 'xuan yi' и т.п.
    """
    if domain not in _CHINA_EN_DOMAIN_NAMES:
        return {}
    with _CHINA_EN_DOMAIN_ALIAS_LOCK:
        cached = _CHINA_EN_DOMAIN_ALIAS_CACHE.get(domain)
        if cached is not None:
            return cached
        aliases: Dict[str, str] = {}
        bucket = ((_china_static_maps().get("en") or {}).get(domain) or {})
        for original, english in bucket.items():
            eng = _as_text(english)
            if not eng:
                continue
            k_eng = _alias_key(eng)
            if k_eng:
                aliases[k_eng] = eng
            src = _as_text(original)
            if not src:
                continue
            k_src = _alias_key(src)
            if k_src and k_src not in aliases:
                aliases[k_src] = eng
            if detect_lang(src) == "zh":
                rom = _romanize_zh(src)
                for cand in (rom, rom.replace("-", " "), rom.replace("-", ""), rom.replace(" ", "")):
                    k = _alias_key(cand)
                    if k and k not in aliases:
                        aliases[k] = eng
        _CHINA_EN_DOMAIN_ALIAS_CACHE[domain] = aliases
        return aliases


def _offline_translate(text: str, *, target_lang: str) -> str:
    s = text.strip()
    if not s:
        return s
    if target_lang == "ru":
        return _RU_TERM_MAP.get(s, s)
    if target_lang == "en":
        if _contains_latin(s):
            return s
        lang = detect_lang(s)
        if lang == "ko":
            return _romanize_ko(s)
        if lang == "zh":
            return _romanize_zh(s)
    return s


@dataclass
class LocalizerStats:
    cache_hits: int = 0
    llm_calls: int = 0
    llm_success: int = 0
    llm_failed: int = 0
    skipped_budget: int = 0


class PgTermLocalizer:
    """
    Перевод терминов с PostgreSQL-кэшем (офлайн: словари + транслитерация).
    LLM/OpenAI убран из рантайма; при необходимости маппинг — отдельные скрипты.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._enabled = False
        self._conn: Optional[psycopg2.extensions.connection] = None
        self.stats = LocalizerStats()
        self._local_cache: Dict[str, str] = {}

    def open(self) -> None:
        self._conn = psycopg2.connect(self._dsn)
        self._conn.autocommit = True
        self._init_schema()
        self._enabled = True

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
        self._enabled = False

    def _init_schema(self) -> None:
        assert self._conn is not None
        with self._conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS term_translation_cache (
                    id BIGSERIAL PRIMARY KEY,
                    source_text TEXT NOT NULL,
                    source_lang TEXT NOT NULL,
                    target_lang TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    translated_text TEXT NOT NULL,
                    provider TEXT NOT NULL DEFAULT 'openai',
                    model TEXT NOT NULL DEFAULT '',
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE (source_text, source_lang, target_lang, domain)
                );
                """
            )

    def _cache_key(self, source_text: str, source_lang: str, target_lang: str, domain: str) -> str:
        return f"{source_lang}|{target_lang}|{domain}|{source_text}"

    def translate(self, text: object, *, target_lang: str, domain: str) -> str:
        s = _as_text(text)
        if not s:
            return ""
        if target_lang == "en" and domain == "mark":
            exact_hit = _KOREA_MARK_EXACT_OVERRIDES.get(s)
            if exact_hit:
                return exact_hit
            china_exact_hit = _CHINA_MARK_EXACT_OVERRIDES.get(s)
            if china_exact_hit:
                return china_exact_hit
            alias_hit = _korea_mark_aliases().get(_alias_key(s))
            if alias_hit:
                return alias_hit
        if target_lang == "en" and domain in _KOREA_EN_DOMAIN_NAMES:
            domain_alias_hit = _korea_en_domain_alias_map_for(domain).get(_alias_key(s))
            if domain_alias_hit:
                return domain_alias_hit

        source_lang = detect_lang(s)
        key = self._cache_key(s, source_lang, target_lang, domain)

        static_hit = _lookup_korea_static(_korea_static_maps(), s, target_lang, domain)
        if not static_hit:
            static_hit = _lookup_china_static(_china_static_maps(), s, target_lang, domain)
        if static_hit:
            self.stats.cache_hits += 1
            if self._enabled:
                self._local_cache[key] = static_hit
            return static_hit

        if target_lang == "en" and _looks_english(s):
            return s

        if not self._enabled:
            return _offline_translate(s, target_lang=target_lang)

        if key in self._local_cache:
            self.stats.cache_hits += 1
            return self._local_cache[key]

        cached = self._read_cache(s, source_lang, target_lang, domain)
        if cached:
            self.stats.cache_hits += 1
            self._local_cache[key] = cached
            return cached

        offline = _offline_translate(s, target_lang=target_lang)
        if offline and offline != s:
            self._write_cache(s, source_lang, target_lang, domain, offline)
            self._local_cache[key] = offline
            return offline

        return s

    def _read_cache(self, source_text: str, source_lang: str, target_lang: str, domain: str) -> Optional[str]:
        assert self._conn is not None
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT translated_text
                FROM term_translation_cache
                WHERE source_text=%s AND source_lang=%s AND target_lang=%s AND domain=%s
                LIMIT 1
                """,
                (source_text, source_lang, target_lang, domain),
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                """
                UPDATE term_translation_cache
                SET hit_count = hit_count + 1, updated_at = now()
                WHERE source_text=%s AND source_lang=%s AND target_lang=%s AND domain=%s
                """,
                (source_text, source_lang, target_lang, domain),
            )
            return str(row[0]).strip() if row[0] is not None else None

    def _write_cache(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        domain: str,
        translated_text: str,
    ) -> None:
        assert self._conn is not None
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO term_translation_cache
                    (source_text, source_lang, target_lang, domain, translated_text, provider, model, hit_count)
                VALUES (%s, %s, %s, %s, %s, 'offline', '', 0)
                ON CONFLICT (source_text, source_lang, target_lang, domain)
                DO UPDATE SET
                    translated_text = EXCLUDED.translated_text,
                    model = EXCLUDED.model,
                    updated_at = now()
                """,
                (source_text, source_lang, target_lang, domain, translated_text),
            )


def localize_car_data(data: Dict[str, object], localizer: PgTermLocalizer) -> None:
    """
    Локализация полей карточки:
    - названия (mark/model/generation/trim/configuration/title) -> EN
    - тех.поля (engine/trans/body/color/drive) -> RU
    """
    def _src(field: str) -> str:
        # Prefer immutable original value (if already saved in previous runs),
        # so old transliteration artifacts do not block static mapping hits.
        return _as_text(data.get(f"{field}_original")) or _as_text(data.get(field))

    name_fields = ("mark", "model", "generation", "configuration", "gradeName", "modelGroupName")
    for f in name_fields:
        v = _src(f)
        if not v:
            continue
        data.setdefault(f"{f}_original", v)
        en = localizer.translate(v, target_lang="en", domain=f)
        if en:
            data[f] = en
            data[f"{f}_en"] = en

    title = " ".join(
        x for x in (_as_text(data.get("mark")), _as_text(data.get("model")), _as_text(data.get("generation"))) if x
    ).strip()
    if title:
        data["title_en"] = title

    drive_target = "en"

    ru_fields = ("engine_type", "transmission_type", "body_type", "color")
    for f in ru_fields:
        v = _src(f)
        if not v:
            continue
        data.setdefault(f"{f}_original", v)
        ru = localizer.translate(v, target_lang="ru", domain=f)
        if ru:
            data[f] = ru
            data[f"{f}_ru"] = ru

    for f in ("drive_type", "prep_drive_type"):
        v = _src(f)
        if not v:
            continue
        data.setdefault(f"{f}_original", v)
        tr = localizer.translate(v, target_lang=drive_target, domain=f)
        if tr:
            data[f] = tr
            data[f"{f}_{drive_target}"] = tr


def localize_china_data(data: Dict[str, object], localizer: PgTermLocalizer) -> None:
    """
    Локализация полей карточки China (Che168 и общий china_static):
    - названия -> EN (приоритет static china map, затем fallback translate)
    - тех.поля -> RU
    """

    def _src(field: str) -> str:
        return _as_text(data.get(f"{field}_original")) or _as_text(data.get(field))

    name_fields = ("mark", "model", "generation", "configuration", "gradeName", "modelGroupName")
    for f in name_fields:
        v = _src(f)
        if not v:
            continue
        data.setdefault(f"{f}_original", v)
        en = localizer.translate(v, target_lang="en", domain=f)
        if en:
            data[f] = en
            data[f"{f}_en"] = en

    title = " ".join(
        x for x in (_as_text(data.get("mark")), _as_text(data.get("model")), _as_text(data.get("generation"))) if x
    ).strip()
    if title:
        data["title_en"] = title

    ru_fields = ("engine_type", "transmission_type", "body_type", "color")
    for f in ru_fields:
        v = _src(f)
        if not v:
            continue
        data.setdefault(f"{f}_original", v)
        ru = localizer.translate(v, target_lang="ru", domain=f)
        if ru:
            data[f] = ru
            data[f"{f}_ru"] = ru

    for f in ("drive_type", "prep_drive_type"):
        v = _src(f)
        if not v:
            continue
        data.setdefault(f"{f}_original", v)
        ru = localizer.translate(v, target_lang="ru", domain=f)
        if ru:
            data[f] = ru
            data[f"{f}_ru"] = ru


def facet_canonical_english(text: object, domain: str) -> str:
    """
    Статическая канонизация для Meilisearch-фасетов и заголовков каталога (без БД).
    Дублирует «раннюю» ветку translate() для EN, чтобы схлопнуть a-udi→Audi и корейские ключи.
    """
    s = _as_text(text)
    if not s:
        return ""
    if domain == "mark":
        exact_hit = _KOREA_MARK_EXACT_OVERRIDES.get(s)
        if exact_hit:
            return exact_hit
        china_exact_hit = _CHINA_MARK_EXACT_OVERRIDES.get(s)
        if china_exact_hit:
            return china_exact_hit
        alias_hit = _korea_mark_aliases().get(_alias_key(s))
        if alias_hit:
            return alias_hit
        dm = _korea_en_domain_alias_map_for("mark").get(_alias_key(s))
        if dm:
            return dm
        static_hit = _lookup_korea_static(_korea_static_maps(), s, "en", "mark")
        if not static_hit:
            static_hit = _lookup_china_static(_china_static_maps(), s, "en", "mark")
        if static_hit:
            return static_hit
        cm = _china_en_domain_alias_map_for("mark").get(_alias_key(s))
        if cm:
            return cm
        if _looks_english(s):
            return s
        if detect_lang(s) == "ko":
            return _romanize_ko(s)
        return s
    if domain in _KOREA_EN_DOMAIN_NAMES:
        dm = _korea_en_domain_alias_map_for(domain).get(_alias_key(s))
        if dm:
            return dm
    if domain in _CHINA_EN_DOMAIN_NAMES:
        cm = _china_en_domain_alias_map_for(domain).get(_alias_key(s))
        if cm:
            return cm
    static_hit = _lookup_korea_static(_korea_static_maps(), s, "en", domain)
    if not static_hit:
        static_hit = _lookup_china_static(_china_static_maps(), s, "en", domain)
    if static_hit:
        return static_hit
    if domain == "trim_name":
        sh2 = _lookup_korea_static(_korea_static_maps(), s, "en", "configuration")
        if not sh2:
            sh2 = _lookup_china_static(_china_static_maps(), s, "en", "configuration")
        if sh2:
            return sh2
    if domain in {"trim_name", "configuration", "gradeName", "modelGroupName"}:
        # Listing-style trims: romanize+cleanup strips CJK and can leave only displacement (e.g. 1.5L) or a bare Latin prefix.
        if _ZH_RE.search(s) and (_LATIN_RE.search(s) or "款" in s or len(s) >= 10):
            return s.strip()
    if _looks_english(s):
        out = _cleanup_china_en_text(s, domain=domain)
        return out or s
    if detect_lang(s) == "ko":
        return _romanize_ko(s)
    if detect_lang(s) == "zh":
        s = _romanize_zh(s)
    out = _cleanup_china_en_text(s, domain=domain)
    return out or s
