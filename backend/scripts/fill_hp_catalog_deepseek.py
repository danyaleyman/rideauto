#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import requests

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from hp_catalog_store import DEFAULT_DB_PATH, connect, ensure_schema, hp_to_kw

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
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


def _query_deepseek(api_key: str, model: str, prompt: str, timeout_sec: int) -> tuple[Optional[int], str]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 120,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=timeout_sec)
    r.raise_for_status()
    answer = ((r.json().get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    hp = _extract_hp(str(answer))
    return hp, str(answer).strip()


def main() -> int:
    p = argparse.ArgumentParser(description="Fill pending hp/kw rows in hp_catalog.db via DeepSeek")
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to hp_catalog.db")
    p.add_argument("--batch-size", type=int, default=100, help="Rows fetched from DB per loop")
    p.add_argument("--max-rows", type=int, default=0, help="Max rows to process (0 = unlimited)")
    p.add_argument("--sleep-sec", type=float, default=0.4, help="Delay between API calls")
    p.add_argument("--timeout-sec", type=int, default=45, help="HTTP timeout per request")
    p.add_argument("--model", default="deepseek-chat", help="DeepSeek model")
    p.add_argument("--retry-errors", action="store_true", help="Retry rows with llm_status='error'")
    args = p.parse_args()

    api_key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        print("Set DEEPSEEK_API_KEY in environment.")
        return 2

    conn = connect(args.db)
    ensure_schema(conn)

    processed = 0
    filled = 0
    no_data = 0
    errors = 0

    status_filter = "llm_status IN ('pending', 'no_data')" if not args.retry_errors else "llm_status IN ('pending', 'no_data', 'error')"

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
            ORDER BY id ASC
            LIMIT ?
            """,
            (left,),
        ).fetchall()
        if not rows:
            break

        for row in rows:
            processed += 1
            prompt = _build_prompt(row)
            try:
                hp, answer = _query_deepseek(api_key, args.model, prompt, args.timeout_sec)
                if hp is not None:
                    conn.execute(
                        """
                        UPDATE hp_catalog
                        SET power_hp=?, power_kw=?, llm_status='done', llm_model=?, llm_reason=?,
                            llm_attempts=llm_attempts+1,
                            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                        WHERE id=?
                        """,
                        (hp, hp_to_kw(hp), args.model, answer[:500], row["id"]),
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
                        (args.model, answer[:500], row["id"]),
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
                    (args.model, str(e)[:500], row["id"]),
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
