from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, Optional

import httpx
import psycopg2


_KO_RE = re.compile(r"[\uac00-\ud7af]")
_ZH_RE = re.compile(r"[\u4e00-\u9fff]")


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


@dataclass
class LocalizerStats:
    cache_hits: int = 0
    llm_calls: int = 0
    llm_success: int = 0
    llm_failed: int = 0
    skipped_budget: int = 0


class PgTermLocalizer:
    """
    Перевод терминов с PostgreSQL-кэшем.
    - target=en для названий (mark/model/generation/trim)
    - target=ru для тех. полей
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._enabled = False
        self._conn: Optional[psycopg2.extensions.connection] = None
        self._client: Optional[httpx.Client] = None
        self._api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
        self._model = (os.environ.get("WRA_TRANSLATION_MODEL") or "gpt-4o-mini").strip()
        self._max_new_terms = int(os.environ.get("WRA_TRANSLATION_MAX_NEW_TERMS") or "400")
        self._new_terms_used = 0
        self.stats = LocalizerStats()
        self._local_cache: Dict[str, str] = {}

    def open(self) -> None:
        if not self._api_key:
            return
        self._conn = psycopg2.connect(self._dsn)
        self._conn.autocommit = True
        self._client = httpx.Client(timeout=25.0)
        self._init_schema()
        self._enabled = True

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
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
        if target_lang == "en" and _looks_english(s):
            return s
        if not self._enabled:
            return s

        source_lang = detect_lang(s)
        key = self._cache_key(s, source_lang, target_lang, domain)
        if key in self._local_cache:
            self.stats.cache_hits += 1
            return self._local_cache[key]

        cached = self._read_cache(s, source_lang, target_lang, domain)
        if cached:
            self.stats.cache_hits += 1
            self._local_cache[key] = cached
            return cached

        if self._new_terms_used >= max(0, self._max_new_terms):
            self.stats.skipped_budget += 1
            return s

        self._new_terms_used += 1
        translated = self._llm_translate(s, source_lang=source_lang, target_lang=target_lang, domain=domain)
        if not translated:
            self.stats.llm_failed += 1
            return s

        self.stats.llm_success += 1
        self._write_cache(s, source_lang, target_lang, domain, translated)
        self._local_cache[key] = translated
        return translated

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
                VALUES (%s, %s, %s, %s, %s, 'openai', %s, 0)
                ON CONFLICT (source_text, source_lang, target_lang, domain)
                DO UPDATE SET
                    translated_text = EXCLUDED.translated_text,
                    model = EXCLUDED.model,
                    updated_at = now()
                """,
                (source_text, source_lang, target_lang, domain, translated_text, self._model),
            )

    def _llm_translate(self, text: str, *, source_lang: str, target_lang: str, domain: str) -> str:
        assert self._client is not None
        self.stats.llm_calls += 1

        role = (
            "You are a strict automotive term translator. "
            "Return only translated text, no explanations, no quotes."
        )
        task = (
            f"Translate source language '{source_lang}' to '{target_lang}' for automotive domain '{domain}'. "
            "Keep brand/model naming style natural. Keep numbers/codes unchanged."
        )

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": role},
                {"role": "user", "content": f"{task}\n\nTEXT:\n{text}"},
            ],
            "temperature": 0,
        }
        try:
            r = self._client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
            r.raise_for_status()
            obj = r.json()
            out = (
                (((obj.get("choices") or [{}])[0]).get("message") or {}).get("content")
                if isinstance(obj, dict)
                else None
            )
            if not out:
                return ""
            return str(out).strip()
        except Exception:
            return ""


def localize_car_data(data: Dict[str, object], localizer: PgTermLocalizer) -> None:
    """
    Локализация полей карточки:
    - названия (mark/model/generation/trim/configuration/title) -> EN
    - тех.поля (engine/trans/body/color/drive) -> RU
    """
    name_fields = ("mark", "model", "generation", "configuration", "gradeName")
    for f in name_fields:
        v = _as_text(data.get(f))
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

    ru_fields = ("engine_type", "transmission_type", "body_type", "color", "drive_type", "prep_drive_type")
    for f in ru_fields:
        v = _as_text(data.get(f))
        if not v:
            continue
        data.setdefault(f"{f}_original", v)
        ru = localizer.translate(v, target_lang="ru", domain=f)
        if ru:
            data[f] = ru
            data[f"{f}_ru"] = ru
