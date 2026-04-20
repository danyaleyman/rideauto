#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

import requests

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from hp_catalog_store import DEFAULT_DB_PATH, connect, ensure_schema, hp_to_kw

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_hp(answer: str) -> Optional[int]:
    if not answer:
        return None
    m = JSON_BLOCK_RE.search(answer)
    if m:
        try:
            payload = json.loads(m.group(0))
            hp = payload.get("hp")
            if hp is not None:
                hp_i = int(hp)
                if 20 <= hp_i <= 2500:
                    return hp_i
                return None
        except Exception:
            pass
    nums = re.findall(r"\d+", answer)
    if not nums:
        return None
    hp_i = int(nums[0])
    if 20 <= hp_i <= 2500:
        return hp_i
    return None


def _build_prompt(row: dict) -> str:
    return (
        "Return ONLY JSON: {\"hp\": <integer or null>, \"confidence\": <0..1>, \"reason\": \"short\"}.\n"
        "Task: determine gross engine power in horsepower (metric PS/hp acceptable).\n"
        f"manufacturer={row['manufacturer']}\n"
        f"model={row['model']}\n"
        f"version={row['version']}\n"
        f"engine_type={row['engine_type']}\n"
        f"displacement_cc={row['displacement_cc']}\n"
        f"year_month={row['year_month']}\n"
        "If unknown, set hp=null."
    )


def _api_call(url: str, api_key: str, model: str, prompt: str, timeout_sec: int) -> Tuple[Optional[int], str]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 120,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
    r.raise_for_status()
    answer = ((r.json().get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    hp = _extract_hp(str(answer))
    return hp, str(answer).strip()


def _query_model(
    prompt: str,
    timeout_sec: int,
    provider: str,
    deepseek_key: str,
    deepseek_model: str,
    openai_key: str,
    openai_model: str,
) -> Tuple[Optional[int], str, str]:
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
            hp, answer = _api_call(DEEPSEEK_URL, deepseek_key, deepseek_model, prompt, timeout_sec)
            return hp, answer, deepseek_model
        if p == "openai":
            if not openai_key:
                errors.append("openai: missing OPENAI_API_KEY")
                continue
            hp, answer = _api_call(OPENAI_URL, openai_key, openai_model, prompt, timeout_sec)
            return hp, answer, openai_model
    raise RuntimeError("; ".join(errors) if errors else "no provider available")


def _status_filter_clause(retry_errors: bool, include_done: bool) -> str:
    if include_done:
        return "1=1"
    if retry_errors:
        return "llm_status IN ('pending', 'no_data', 'error')"
    return "llm_status IN ('pending', 'no_data')"


def main() -> int:
    p = argparse.ArgumentParser(description="Fill pending hp/kw rows in hp_catalog.db via DeepSeek")
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to hp_catalog.db")
    p.add_argument("--batch-size", type=int, default=100, help="Rows fetched from DB per loop")
    p.add_argument("--max-rows", type=int, default=0, help="Max rows to process (0 = unlimited)")
    p.add_argument("--sleep-sec", type=float, default=0.4, help="Delay between API calls")
    p.add_argument("--timeout-sec", type=int, default=45, help="HTTP timeout per request")
    p.add_argument("--provider", default="auto", help="deepseek | openai | auto")
    p.add_argument("--model", default="deepseek-chat", help="DeepSeek model")
    p.add_argument("--openai-model", default="gpt-4o-mini", help="OpenAI model")
    p.add_argument("--retry-errors", action="store_true", help="Retry rows with llm_status='error'")
    p.add_argument("--continuous", action="store_true", help="Do not exit when queue is empty")
    p.add_argument("--idle-sleep-sec", type=float, default=30.0, help="Sleep when queue is empty in --continuous mode")
    p.add_argument("--max-attempts", type=int, default=0, help="Skip rows where llm_attempts >= this value (0 disables)")
    p.add_argument("--include-done", action="store_true", help="Also re-check rows with llm_status='done'")
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

    conn = connect(args.db)
    ensure_schema(conn)

    processed = 0
    filled = 0
    no_data = 0
    errors = 0

    status_filter = _status_filter_clause(args.retry_errors, args.include_done)

    while True:
        if args.max_rows > 0 and processed >= args.max_rows:
            break
        left = args.batch_size
        if args.max_rows > 0:
            left = min(left, args.max_rows - processed)
        rows = conn.execute(
            f"""
            SELECT id, manufacturer, model, version, engine_type, displacement_cc, year_month, llm_attempts
            FROM hp_catalog
            WHERE (power_hp IS NULL OR power_hp <= 0) AND {status_filter}
              AND (? <= 0 OR llm_attempts < ?)
            ORDER BY id ASC
            LIMIT ?
            """,
            (args.max_attempts, args.max_attempts, left),
        ).fetchall()
        if not rows:
            if args.continuous:
                time.sleep(max(0.0, args.idle_sleep_sec))
                continue
            break

        for row in rows:
            processed += 1
            prompt = _build_prompt(row)
            try:
                hp, answer, used_model = _query_model(
                    prompt=prompt,
                    timeout_sec=args.timeout_sec,
                    provider=provider,
                    deepseek_key=deepseek_key,
                    deepseek_model=args.model,
                    openai_key=openai_key,
                    openai_model=args.openai_model,
                )
                if hp is not None:
                    conn.execute(
                        """
                        UPDATE hp_catalog
                        SET power_hp=?, power_kw=?, llm_status='done', llm_model=?, llm_reason=?,
                            llm_attempts=llm_attempts+1,
                            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                        WHERE id=?
                        """,
                        (hp, hp_to_kw(hp), used_model, answer[:500], row["id"]),
                    )
                    filled += 1
                else:
                    conn.execute(
                        """
                        UPDATE hp_catalog
                        SET llm_status='no_data', llm_model=?, llm_reason=?,
                            llm_attempts=llm_attempts+1,
                            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                        WHERE id=?
                        """,
                        (used_model, answer[:500], row["id"]),
                    )
                    no_data += 1
            except Exception as e:
                errors += 1
                conn.execute(
                    """
                    UPDATE hp_catalog
                    SET llm_status='error', llm_model=?, llm_reason=?,
                        llm_attempts=llm_attempts+1,
                        updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                    WHERE id=?
                    """,
                    (f"{provider}-error", str(e)[:500], row["id"]),
                )
            conn.commit()
            if args.sleep_sec > 0:
                time.sleep(args.sleep_sec)

        print(
            f"progress processed={processed} filled={filled} no_data={no_data} errors={errors}",
            flush=True,
        )

    print(
        f"done processed={processed} filled={filled} no_data={no_data} errors={errors}",
        flush=True,
    )
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
