#!/usr/bin/env python3
"""
Локальный смоук Che168 API без PostgreSQL: N листингов → carinfo + spec + нормализация.
Требуется che168.deviceid (YAML или CHE168_DEVICE_ID).

  cd backend
  python scripts/che168_smoke_fetch.py --config ../che168_scraper.yaml --limit 5
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from encar_scraper import load_config  # noqa: E402
from scraper_pipeline.che168.parser import (  # noqa: E402
    che168_listing_numeric_id,
    parse_one_che168_car_sync,
)
from scraper_pipeline.che168.workers import (  # noqa: E402
    che168_search_items,
    che168_brand_rows,
    che168_brand_id,
    _api_layer_list,
    _returncode_ok,
)
from scraper_pipeline.che168.client import AsyncChe168Client  # noqa: E402


async def _amain(args: argparse.Namespace) -> int:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log = logging.getLogger("che168_smoke")
    config = load_config(str(Path(args.config).expanduser().resolve()))
    _dev = (os.environ.get("CHE168_DEVICE_ID") or os.environ.get("CHE168_DEVICEID") or "").strip()
    if _dev:
        config.setdefault("che168", {})["deviceid"] = _dev
    if not str((config.get("che168") or {}).get("deviceid", "")).strip():
        print("Задайте che168.deviceid в YAML или CHE168_DEVICE_ID", file=sys.stderr)
        return 2

    if args.bootstrap:
        try:
            from scraper_pipeline.che168.session_playwright import apply_playwright_bootstrap_to_config

            log.info("smoke: Playwright bootstrap…")
            await asyncio.to_thread(apply_playwright_bootstrap_to_config, config, log)
        except ImportError as e:
            print(e, file=sys.stderr)
            return 7
    ch = config.get("che168", {}) or {}

    limit = max(1, min(50, int(args.limit)))
    brand_id = int(args.brand_id) if args.brand_id is not None else None

    async with AsyncChe168Client(config, log) as client:
        b_raw, st, err = await client.fetch_brands()
        if st != 200 or not b_raw or not _returncode_ok(b_raw):
            print(f"/brand failed status={st} err={err}", file=sys.stderr)
            return 3
        rows = che168_brand_rows(b_raw)
        if not rows:
            print("No brands in /brand response", file=sys.stderr)
            return 4

        if ch.get("taxonomy_sync_from_brand_api", True):
            from scraper_pipeline.che168.taxonomy_sync import merge_che168_taxonomy_with_brand_api

            yaml_tax = dict(ch.get("taxonomy")) if isinstance(ch.get("taxonomy"), dict) else {}
            ch["taxonomy"] = merge_che168_taxonomy_with_brand_api(b_raw, yaml_tax)

        from scraper_pipeline.che168.taxonomy_sync import sync_che168_series_taxonomy

        await sync_che168_series_taxonomy(client, config, log)

        async def _search_for_brand(bid: int) -> tuple[Any, int, Optional[str]]:
            r, s, e = await client.fetch_search(
                brandid=bid,
                pageindex=1,
                pagesize=max(limit, 10),
                sort=int(ch.get("search_sort", 0)),
                vehicle_list=int(ch.get("vehicle_list", 0)),
            )
            return r, s, e

        candidates: List[int] = []
        if brand_id is not None:
            candidates.append(brand_id)
        for row in rows[:50]:
            bid = che168_brand_id(row)
            if bid is not None and bid not in candidates:
                candidates.append(bid)

        raw: Any = None
        used_bid: Optional[int] = None
        last_layer: dict = {}
        last_ok_raw: Any = None
        for bid in candidates:
            r, s, e = await _search_for_brand(bid)
            if s != 200 or not r or not _returncode_ok(r):
                log.debug("smoke: brand %s search skip http=%s err=%s", bid, s, e)
                continue
            last_ok_raw = r
            layer = _api_layer_list(r)
            last_layer = layer
            items_try = che168_search_items(r)
            if items_try:
                raw = r
                used_bid = bid
                log.info("smoke: brand_id=%s totalcount=%s items=%s", bid, layer.get("totalcount"), len(items_try))
                break

        if not raw:
            raw = last_ok_raw
        if not raw:
            print("/search: нет успешных ответов API для перебранных брендов", file=sys.stderr)
            return 5

        items = che168_search_items(raw)
        if not items:
            cl = last_layer.get("carlist")
            print(
                f"No list items after scanning brands keys={list(last_layer.keys())[:20]} "
                f"totalcount={last_layer.get('totalcount')} "
                f"carlist_len={len(cl) if isinstance(cl, list) else 'n/a'} tried={len(candidates)}",
                file=sys.stderr,
            )
            if int(last_layer.get("totalcount") or 0) == 0:
                print(
                    "Если везде totalcount=0: регион/IP, пустой каталог, или усиленная антибот-политика. "
                    "Проверьте прокси (sticky + тот же IP, что при bootstrap).",
                    file=sys.stderr,
                )
            return 6

        picked: List[Dict[str, Any]] = []
        for it in items:
            if len(picked) >= limit:
                break
            ext = che168_listing_numeric_id(it)
            if ext:
                picked.append({"id": ext, "list_item": it})

        out: List[Dict[str, Any]] = []
        for p in picked:
            ext = p["id"]
            li = p["list_item"]
            info, sti, ei = await client.fetch_carinfo(ext)
            ci = info if isinstance(info, dict) else {}
            layer = ci.get("result") if isinstance(ci.get("result"), dict) else ci
            if not isinstance(layer, dict):
                layer = {}
            specid = layer.get("specid") or layer.get("specId")
            sparam, s1, _ = await client.fetch_specparam(str(specid)) if specid else (None, 0, None)
            scfg, s2, _ = await client.fetch_specconfig(str(specid)) if specid else (None, 0, None)
            rec, _, _ = await client.fetch_recommend(infoid=ext, pageindex=1, pagesize=10)
            dealerid = layer.get("dealerid") or layer.get("dealerId")
            pkey = layer.get("paramkey") or layer.get("paramKey") or ""
            rep = None
            if dealerid and pkey:
                rep, _, _ = await client.fetch_report_summary(str(dealerid).strip(), str(pkey).strip())

            hints: Dict[str, str] = {}
            _a = client.get_initial_cookie("area")
            _io = client.get_initial_cookie("is_overseas")
            if _a:
                hints["area"] = _a
            if _io:
                hints["is_overseas"] = _io
            tax = ch.get("taxonomy") if isinstance(ch.get("taxonomy"), dict) else None

            lc = ch.get("listing_cluster") if isinstance(ch.get("listing_cluster"), dict) else None

            norm = parse_one_che168_car_sync(
                external_id=str(ext),
                list_item=li,
                carinfo=layer,
                specparam=sparam if isinstance(sparam, dict) else None,
                specconfig=scfg if isinstance(scfg, dict) else None,
                recommend=rec if isinstance(rec, dict) else None,
                report_summary=rep if isinstance(rep, dict) else None,
                assume_price_wan_yuan=bool(ch.get("assume_price_in_wan_yuan", False)),
                taxonomy=tax,
                session_cookie_hints=hints if hints else None,
                listing_cluster=lc,
            )
            out.append(
                {
                    "infoid": ext,
                    "http_carinfo": sti,
                    "err_carinfo": ei,
                    "normalized": norm,
                }
            )

    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--brand-id", type=int, default=None, help="Иначе первый из GET /brand")
    p.add_argument(
        "--bootstrap",
        action="store_true",
        help="Сначала Chromium на том же прокси что API → куки + фиксация _session_proxy_url",
    )
    args = p.parse_args()
    raise SystemExit(asyncio.run(_amain(args)))


if __name__ == "__main__":
    main()
