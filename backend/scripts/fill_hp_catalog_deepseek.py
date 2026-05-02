#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Optional, Tuple

import requests
from filelock import FileLock, Timeout as FileLockTimeout

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from hp_catalog_store import (
    DEFAULT_DB_PATH,
    connect,
    ensure_llm_prompt_cache_schema,
    ensure_schema,
    evict_llm_prompt_cache,
    hp_to_kw,
    llm_prompt_cache_get,
    llm_prompt_cache_put,
)
from hp_secondary_review import finalize_review_fields
from power_from_external import invalidate_hp_catalog_cache

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

DEFAULT_PROMPT_VERSION = "2026-05-02"

class HttpPostsBudgetReached(Exception):
    """Превышен лимит HTTP POST (повторные попытки учитываются)."""


def _prompt_version_tag() -> str:
    return (os.environ.get("HP_LLM_PROMPT_VERSION") or DEFAULT_PROMPT_VERSION).strip() or DEFAULT_PROMPT_VERSION


def _prompt_hash_short(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:20]


def _prompt_hash_full(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _clamp_float01(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return None
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, x))


def _sanity_hp_for_row(displacement_cc: Any, hp: int, engine_type: str) -> bool:
    if not (25 <= hp <= 2500):
        return False
    et_raw = str(engine_type or "").lower()
    ko = str(engine_type or "")
    if any(x in ko for x in ("전기",)):
        et_raw = f"{et_raw} electric hint"
    if "electric" in et_raw or "ev " in et_raw or et_raw.strip() in ("ev",):
        return hp <= 2000

    cc: Optional[int] = None
    if displacement_cc is not None:
        try:
            cc_i = int(displacement_cc)
            if cc_i > 0:
                cc = cc_i
        except (TypeError, ValueError):
            cc = None
    if cc is None or cc < 400:
        return True

    liters = cc / 1000.0
    ratio = hp / liters if liters > 1e-6 else 999.0
    if ratio > 280:
        return False
    if cc >= 1200 and ratio < 18:
        return False
    return True


def _extract_hp_and_conf_detail(answer: str) -> Tuple[Optional[int], Optional[float], bool]:
    """Третий флаг — ответ содержит распарсенный JSON-объект с ключом hp (значение может быть null)."""
    if not answer:
        return None, None, False
    confidence: Optional[float] = None
    structured_hp_json = False
    m = JSON_BLOCK_RE.search(answer)
    if m:
        try:
            payload = json.loads(m.group(0))
            if isinstance(payload, dict) and "hp" in payload:
                structured_hp_json = True
                hp = payload.get("hp")
                confidence = _clamp_float01(payload.get("confidence"))
                if hp is not None and hp != "":
                    try:
                        hp_i = int(hp)
                    except (TypeError, ValueError):
                        return None, confidence, structured_hp_json
                    if 20 <= hp_i <= 2500:
                        return hp_i, confidence, structured_hp_json
                return None, confidence, structured_hp_json
        except Exception:
            pass
    nums = re.findall(r"\d+", answer)
    if not nums:
        return None, confidence, False
    hp_i = int(nums[0])
    if 20 <= hp_i <= 2500:
        return hp_i, confidence, False
    return None, confidence, False


def _extract_hp_and_conf(answer: str) -> Tuple[Optional[int], Optional[float]]:
    hp, conf, _ = _extract_hp_and_conf_detail(answer)
    return hp, conf


def _build_prompt(row: dict) -> str:
    mc = str(row.get("motor_code_norm") or "").strip()
    vp = str(row.get("vin_prefix") or "").strip()
    extra = ""
    if mc or vp:
        extra = f"motor_code_norm={mc or 'n/a'}\nvin_prefix (11 chars if known)={vp or 'n/a'}\n"
    return (
        "Return ONLY compact JSON:\n"
        '{"hp": <integer or null>, "confidence": <number 0..1>, "reason": "<=120 chars>"}\n'
        "Task: manufacturer's rated engine power at the crank in metric horsepower "
        "(PS ≈ DIN hp; ignore kW unless you convert to hp as hp ≈ kW/0.7355).\n"
        "confidence: your certainty based on typical factory specs for this exact trim/year/volume "
        "(0 if guessing from similar engines only).\n"
        f"manufacturer={row['manufacturer']}\n"
        f"model={row['model']}\n"
        f"version / trim={row['version']}\n"
        f"engine_type / fuel hint={row['engine_type']}\n"
        f"{extra}"
        f"displacement_cc={row['displacement_cc']}\n"
        f"year_month={row['year_month']}\n"
        "If unknown or ambiguous across trims, hp=null confidence<=0.3."
    )


def _int_env(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _retry_http_single_llm_chat(
    *,
    http_budget: dict[str, int],
    max_http_posts: int,
    latencies_ms: Optional[list[float]],
    url: str,
    api_key: str,
    model: str,
    prompt: str,
    timeout_sec: int,
) -> Tuple[Optional[int], Optional[float], str]:
    """Ретрай HTTP; каждый POST увеличивает http_budget[\"posts\"]."""
    max_retries = max(1, _int_env("HP_LLM_MAX_RETRIES", 5))
    last_err: Optional[BaseException] = None
    for attempt in range(max_retries):
        try:
            if max_http_posts > 0 and http_budget.get("posts", 0) >= max_http_posts:
                raise HttpPostsBudgetReached()
            http_budget["posts"] = http_budget.get("posts", 0) + 1
            if max_http_posts > 0 and http_budget["posts"] > max_http_posts:
                raise HttpPostsBudgetReached()
            return _single_api_post_for_retry(
                url,
                api_key,
                model,
                prompt,
                timeout_sec,
                latencies_ms=latencies_ms,
                http_budget=http_budget,
            )
        except HttpPostsBudgetReached:
            raise
        except requests.HTTPError as e:
            last_err = e
            resp = getattr(e, "response", None)
            code = getattr(resp, "status_code", None) if resp is not None else None
            if code not in (429, 408) and not (code is not None and 500 <= code < 600):
                raise
            if attempt >= max_retries - 1:
                raise
            base = min(60.0, 2.0**attempt)
            jitter = random.uniform(0.0, 0.35 * base)
            time.sleep(base + jitter)
        except requests.RequestException as e:
            last_err = e
            if attempt >= max_retries - 1:
                raise
            base = min(45.0, 1.5**attempt)
            time.sleep(base + random.uniform(0.0, 0.25 * base))
    assert last_err is not None
    raise last_err


def _single_api_post_for_retry(
    url: str,
    api_key: str,
    model: str,
    prompt: str,
    timeout_sec: int,
    *,
    latencies_ms: Optional[list[float]] = None,
) -> Tuple[Optional[int], Optional[float], str]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 160,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    t0 = time.perf_counter()
    r = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
    if latencies_ms is not None:
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)
    r.raise_for_status()
    answer = ((r.json().get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    hp, conf, json_hp_ok = _extract_hp_and_conf_detail(str(answer))
    if http_budget is not None and not json_hp_ok:
        http_budget["http_posts_without_structured_hp_json"] = (
            http_budget.get("http_posts_without_structured_hp_json", 0) + 1
        )
    return hp, conf, str(answer).strip()


def _call_llm_chat(
    url: str,
    api_key: str,
    model: str,
    prompt: str,
    timeout_sec: int,
    *,
    http_budget: dict[str, int],
    max_http_posts: int,
    latencies_ms: Optional[list[float]],
) -> Tuple[Optional[int], Optional[float], str]:
    """Один семантический запрос провайдеру с ретраями; каждый HTTP POST учитывает http_budget[\"posts\"]."""
    return _retry_http_single_llm_chat(
        http_budget=http_budget,
        max_http_posts=max_http_posts,
        latencies_ms=latencies_ms,
        url=url,
        api_key=api_key,
        model=model,
        prompt=prompt,
        timeout_sec=timeout_sec,
    )


def _query_model(
    prompt: str,
    timeout_sec: int,
    provider: str,
    deepseek_key: str,
    deepseek_model: str,
    openai_key: str,
    openai_model: str,
    *,
    http_budget: dict[str, int],
    max_http_posts: int,
    latencies_ms: Optional[list[float]],
) -> Tuple[Optional[int], Optional[float], str, str]:
    provider = (provider or "deepseek").strip().lower()
    if provider not in ("deepseek", "openai", "auto"):
        raise ValueError("provider must be deepseek/openai/auto")

    errors = []
    order = [provider] if provider in ("deepseek", "openai") else ["deepseek", "openai"]
    for p in order:
        if p == "deepseek":
            if not deepseek_key:
                errors.append("deepseek: missing DEEPSEEK_API_KEY")
                continue
            hp, confidence, answer = _call_llm_chat(
                DEEPSEEK_URL,
                deepseek_key,
                deepseek_model,
                prompt,
                timeout_sec,
                http_budget=http_budget,
                max_http_posts=max_http_posts,
                latencies_ms=latencies_ms,
            )
            return hp, confidence, answer, deepseek_model
        if p == "openai":
            if not openai_key:
                errors.append("openai: missing OPENAI_API_KEY")
                continue
            hp, confidence, answer = _call_llm_chat(
                OPENAI_URL,
                openai_key,
                openai_model,
                prompt,
                timeout_sec,
                http_budget=http_budget,
                max_http_posts=max_http_posts,
                latencies_ms=latencies_ms,
            )
            return hp, confidence, answer, openai_model
    raise RuntimeError("; ".join(errors) if errors else "no provider available")


def _status_filter_clause(retry_errors: bool, include_done: bool) -> str:
    if include_done:
        return "1=1"
    if retry_errors:
        return "llm_status IN ('pending', 'no_data', 'error')"
    return "llm_status IN ('pending', 'no_data')"


def _cache_enabled(cli_flag: bool) -> bool:
    if cli_flag:
        return False
    return str(os.environ.get("HP_LLM_PROMPT_CACHE", "1")).strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Fill pending hp/kw rows in hp_catalog.db via DeepSeek")
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to hp_catalog.db")
    p.add_argument("--batch-size", type=int, default=100, help="Rows fetched from DB per loop")
    p.add_argument("--max-rows", type=int, default=0, help="Max каталожных строк (0 = без лимита)")
    p.add_argument(
        "--max-row-iterations",
        "--max-api-calls",
        type=int,
        dest="max_api_calls",
        default=_int_env("HP_LLM_MAX_CALLS_PER_RUN", 0),
        help=(
            "Stop after обработано N строк (каждый деqueued row; вкл. попадание в промпт‑кеш; "
            "env HP_LLM_MAX_CALLS_PER_RUN). Ретраи того же деqueued row отдельно копят http_posts."
        ),
    )
    p.add_argument(
        "--max-http-posts",
        type=int,
        default=_int_env("HP_LLM_MAX_HTTP_POSTS_PER_RUN", 0),
        help="Лимит HTTP POST суммарно включая retries (0 = ∞; env HP_LLM_MAX_HTTP_POSTS_PER_RUN)",
    )
    p.add_argument("--sleep-sec", type=float, default=0.4, help="Delay between API calls")
    p.add_argument("--timeout-sec", type=int, default=45, help="HTTP timeout per request")
    p.add_argument("--provider", default="auto", help="deepseek | openai | auto")
    p.add_argument("--model", default="deepseek-chat", help="DeepSeek model")
    p.add_argument("--openai-model", default="gpt-4o-mini", help="OpenAI model")
    p.add_argument("--retry-errors", action="store_true", help="Retry rows with llm_status='error'")
    p.add_argument("--continuous", action="store_true", help="Do not exit when queue is empty")
    p.add_argument("--idle-sleep-sec", type=float, default=30.0)
    p.add_argument("--max-attempts", type=int, default=0)
    p.add_argument("--include-done", action="store_true")
    p.add_argument(
        "--min-confidence",
        type=float,
        default=float((os.environ.get("HP_LLM_MIN_CONFIDENCE") or "0.72").strip() or "0.72"),
    )
    p.add_argument("--allow-missing-confidence", action="store_true")
    p.add_argument("--no-cache", action="store_true", help="Не использовать hp_llm_prompt_cache")

    idg = p.add_argument_group("параллельные воркеры")
    idg.add_argument("--id-from", type=int, default=0, help="MIN(id)")
    idg.add_argument("--id-to", type=int, default=0, help="MAX(id)")
    idg.add_argument("--shard-mod", type=int, default=0, help="Модуль id (>=2 включает шардирование)")
    idg.add_argument("--shard-rem", type=int, default=0, help="id % shard_mod == shard-rem")

    lk = p.add_argument_group("lock")
    lk.add_argument(
        "--lock-file",
        type=Path,
        default=None,
        help="Эксклюзивный lock (отдельный файл на каждый воркер/шард)",
    )
    lk.add_argument(
        "--lock-timeout",
        type=float,
        default=3600.0,
        help="Сек до неудачи ожидания lock (filelock)",
    )

    args = p.parse_args()

    deepseek_key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    openai_key = (os.environ.get("OPENAI_API_KEY") or "").strip()

    provider = (args.provider or "auto").strip().lower()
    if provider == "deepseek" and not deepseek_key:
        print("Set DEEPSEEK_API_KEY in environment.")
        return 2
    if provider == "openai" and not openai_key:
        print("Set OPENAI_API_KEY in environment.")
        return 2
    if provider == "auto" and not deepseek_key and not openai_key:
        print("Set DEEPSEEK_API_KEY or OPENAI_API_KEY in environment.")
        return 2

    lock_ctx: Any = nullcontext()
    if args.lock_file is not None:
        args.lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_ctx = FileLock(str(args.lock_file), timeout=float(args.lock_timeout))

    try:
        with lock_ctx:
            return _fill_inner(args, provider, deepseek_key, openai_key)
    except FileLockTimeout:
        print(f"lock timeout: {args.lock_file}", file=sys.stderr, flush=True)
        return 3


def _fill_inner(args: argparse.Namespace, provider: str, deepseek_key: str, openai_key: str) -> int:
    conn = connect(args.db)
    ensure_schema(conn)
    ensure_llm_prompt_cache_schema(conn)

    cache_max_rows = max(0, _int_env("HP_LLM_CACHE_MAX_ROWS", 0))
    try:
        cache_age_days = float((os.environ.get("HP_LLM_CACHE_MAX_AGE_DAYS") or "0").strip() or "0")
    except ValueError:
        cache_age_days = 0.0
    cache_age_days = max(0.0, cache_age_days)
    evicted_n = evict_llm_prompt_cache(conn, max_rows=cache_max_rows, max_age_days=cache_age_days)
    if evicted_n:
        print(
            f"hp_llm_prompt_cache eviction: removed≈{evicted_n} (max_rows={cache_max_rows} max_age_days={cache_age_days})",
            flush=True,
        )
    conn.commit()

    processed = filled = no_data = rejected = errors = 0
    cache_hits = 0
    logical_provider_dispatches = 0
    http_budget = {"posts": 0}

    latencies_ms: list[float] = []
    prompt_ver = _prompt_version_tag()
    min_conf = float(args.min_confidence)
    row_cap = max(0, int(args.max_api_calls))
    http_cap = max(0, int(args.max_http_posts))
    use_cache = _cache_enabled(cli_flag=args.no_cache)

    where_extra_sql = ""
    where_params_tail: Tuple[Any, ...] = ()

    if int(args.id_from) > 0:
        where_extra_sql += " AND id >= ?"
        where_params_tail += (int(args.id_from),)
    if int(args.id_to) > 0:
        where_extra_sql += " AND id <= ?"
        where_params_tail += (int(args.id_to),)
    if int(args.shard_mod) >= 2:
        mod = int(args.shard_mod)
        rem = int(args.shard_rem) % mod
        where_extra_sql += " AND ((id % ?) = ?)"
        where_params_tail += (mod, rem)

    status_filter = _status_filter_clause(args.retry_errors, args.include_done)

    while True:
        if args.max_rows > 0 and processed >= args.max_rows:
            break
        left = args.batch_size
        if args.max_rows > 0:
            left = min(left, args.max_rows - processed)
        if row_cap > 0 and processed >= row_cap:
            break

        qparams: Tuple[Any, ...] = (args.max_attempts, args.max_attempts)
        rows = conn.execute(
            f"""
            SELECT id, manufacturer, model, version, engine_type, displacement_cc, year_month, llm_attempts,
                   motor_code_norm, vin_prefix
            FROM hp_catalog
            WHERE (power_hp IS NULL OR power_hp <= 0) AND {status_filter}
              AND (? <= 0 OR llm_attempts < ?)
              {where_extra_sql}
            ORDER BY id ASC
            LIMIT ?
            """,
            qparams + where_params_tail + (left,),
        ).fetchall()
        if not rows:
            if args.continuous:
                time.sleep(max(0.0, args.idle_sleep_sec))
                continue
            break

        for row in rows:
            if args.max_rows > 0 and processed >= args.max_rows:
                break
            if row_cap > 0 and processed >= row_cap:
                break

            processed += 1
            prompt = _build_prompt(row)
            phash_s = _prompt_hash_short(prompt)
            ph_full = _prompt_hash_full(prompt)

            hp: Optional[int] = None
            conf_from_model: Optional[float] = None
            answer = ""
            used_model = ""

            cache_row = None
            if use_cache:
                cache_row = llm_prompt_cache_get(conn, ph_full)

            try:
                if cache_row:
                    hp = int(cache_row["hp"])
                    try:
                        conf_from_model = float(cache_row["confidence"]) if cache_row["confidence"] is not None else None
                    except (TypeError, ValueError):
                        conf_from_model = None
                    answer = str(cache_row["raw_answer"] or "").strip()
                    used_model = "<prompt-cache>"
                    cache_hits += 1
                else:
                    logical_provider_dispatches += 1
                    hp, conf_from_model, answer, used_model = _query_model(
                        prompt=prompt,
                        timeout_sec=args.timeout_sec,
                        provider=provider,
                        deepseek_key=deepseek_key,
                        deepseek_model=args.model,
                        openai_key=openai_key,
                        openai_model=args.openai_model,
                        http_budget=http_budget,
                        max_http_posts=http_cap,
                        latencies_ms=latencies_ms,
                    )

                effective_conf = conf_from_model
                if effective_conf is None and args.allow_missing_confidence:
                    effective_conf = 0.82

                sane = hp is None or _sanity_hp_for_row(
                    row["displacement_cc"], hp, str(row["engine_type"] or "")
                )
                conf_ok = effective_conf is not None and effective_conf >= min_conf

                rev_flag, rev_txt = (0, "")
                if hp is not None:
                    rev_flag, rev_txt = finalize_review_fields(
                        displacement_cc=row["displacement_cc"],
                        power_hp=int(hp),
                        engine_type=str(row["engine_type"] or ""),
                        motor_code_norm=str(row["motor_code_norm"] or ""),
                        vin_prefix=str(row["vin_prefix"] or ""),
                    )

                if hp is not None and conf_ok and sane:
                    if cache_row is None and hp is not None and use_cache and conf_from_model is not None:
                        llm_prompt_cache_put(
                            conn,
                            prompt_hash_full=ph_full,
                            hp=int(hp),
                            confidence=float(conf_from_model),
                            raw_answer=answer[:2000],
                            llm_prompt_version=prompt_ver,
                        )

                    conn.execute(
                        """
                        UPDATE hp_catalog
                        SET power_hp=?, power_kw=?, llm_status='done', llm_model=?, llm_reason=?,
                            llm_confidence=?,
                            llm_prompt_version=?, llm_prompt_hash=?,
                            review_flag=?, review_note=?,
                            llm_attempts=llm_attempts+1,
                            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                        WHERE id=?
                        """,
                        (
                            hp,
                            hp_to_kw(hp),
                            used_model,
                            answer[:500],
                            round(float(effective_conf), 6),
                            prompt_ver,
                            phash_s,
                            rev_flag,
                            (rev_txt or "")[:200],
                            row["id"],
                        ),
                    )
                    filled += 1
                elif hp is not None:
                    rejected += 1
                    parts: list[str] = []
                    if not conf_ok:
                        parts.append(f"confidence<{min_conf}:{effective_conf}/{conf_from_model}")
                    if not sane:
                        parts.append("failed hp/cc sanity")
                    reason_note = "; ".join(parts) or "rejected"
                    conn.execute(
                        """
                        UPDATE hp_catalog
                        SET llm_status='no_data', llm_model=?, llm_reason=?,
                            llm_confidence=?,
                            llm_prompt_version=?, llm_prompt_hash=?,
                            review_flag=0, review_note='',
                            llm_attempts=llm_attempts+1,
                            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                        WHERE id=?
                        """,
                        (
                            used_model,
                            (reason_note + " | " + answer)[:500],
                            conf_from_model,
                            prompt_ver,
                            phash_s,
                            row["id"],
                        ),
                    )
                    no_data += 1
                else:
                    conn.execute(
                        """
                        UPDATE hp_catalog
                        SET llm_status='no_data', llm_model=?, llm_reason=?,
                            llm_confidence=?,
                            llm_prompt_version=?, llm_prompt_hash=?,
                            review_flag=0, review_note='',
                            llm_attempts=llm_attempts+1,
                            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                        WHERE id=?
                        """,
                        (
                            used_model,
                            answer[:500],
                            conf_from_model,
                            prompt_ver,
                            phash_s,
                            row["id"],
                        ),
                    )
                    no_data += 1
            except HttpPostsBudgetReached:
                print("stop: HTTP posts budget exhausted", flush=True)
                conn.commit()
                _print_done(
                    processed,
                    filled,
                    no_data,
                    rejected,
                    errors,
                    cache_hits,
                    logical_provider_dispatches,
                    http_budget,
                    latencies_ms,
                )
                invalidate_hp_catalog_cache()
                conn.close()
                return 0
            except Exception as e:
                errors += 1
                conn.execute(
                    """
                    UPDATE hp_catalog
                    SET llm_status='error', llm_model=?, llm_reason=?,
                        llm_prompt_version=?, llm_prompt_hash=?,
                        llm_attempts=llm_attempts+1,
                        updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                    WHERE id=?
                    """,
                    (f"{provider}-error", str(e)[:500], prompt_ver, phash_s, row["id"]),
                )
            conn.commit()
            if args.sleep_sec > 0:
                time.sleep(args.sleep_sec)

        print(
            "progress ",
            dict(
                rows_processed=processed,
                filled=filled,
                no_data=no_data,
                rejected=rejected,
                errors=errors,
                cache_hits=cache_hits,
                logical_HTTP_dispatches_miss_cache=logical_provider_dispatches,
                http_posts=http_budget["posts"],
                http_posts_without_structured_hp_json=http_budget.get("http_posts_without_structured_hp_json", 0),
            ),
            flush=True,
        )
        if args.max_rows > 0 and processed >= args.max_rows:
            break
        if row_cap > 0 and processed >= row_cap:
            break
        if http_cap > 0 and http_budget["posts"] >= http_cap:
            break

    _print_done(
        processed,
        filled,
        no_data,
        rejected,
        errors,
        cache_hits,
        logical_provider_dispatches,
        http_budget,
        latencies_ms,
    )
    invalidate_hp_catalog_cache()
    conn.close()
    return 0


def _print_done(
    processed: int,
    filled: int,
    no_data: int,
    rejected: int,
    errors: int,
    cache_hits: int,
    logical_dispatches: int,
    http_budget: dict,
    latencies_ms: list,
) -> None:
    lat_summary = ""
    if latencies_ms:
        s = sorted(latencies_ms)
        lat_summary = f" latency_ms_median={s[len(s) // 2]:.0f} max={s[-1]:.0f} n={len(s)}"
    no_json = http_budget.get("http_posts_without_structured_hp_json", 0)
    print(
        f"done rows_processed={processed} filled={filled} no_data={no_data} rejected={rejected} errors={errors} "
        f"cache_hits={cache_hits} logical_HTTP_dispatches={(logical_dispatches)} http_posts_total={http_budget.get('posts', 0)} "
        f"http_posts_without_structured_hp_json={no_json}{lat_summary}",
        flush=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
