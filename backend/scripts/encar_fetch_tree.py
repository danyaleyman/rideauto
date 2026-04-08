# -*- coding: utf-8 -*-
"""
Сбор дерева бренд / модель / поколение / тип (двигатель, привод) / комплектация с Encar API.
Результаты сохраняются в data/ проекта; build_encar_mapping.py строит encar_mapping.json для фронта.

Запуск из корня проекта:
  python scripts/encar_fetch_tree.py
  python scripts/encar_fetch_tree.py --limit 2
  python scripts/encar_fetch_tree.py --no-import
"""
from pathlib import Path
import argparse
import csv
import json
import sys
import time
import urllib.parse
import requests

# Результаты в data/ (репозиторий)
REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "data"
OUTPUT_DIR.mkdir(exist_ok=True)

BASE = "https://api.encar.com/search/car/list/general"
HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Origin": "https://www.encar.com",
    "Referer": "https://www.encar.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
}
INAV = "|Metadata|Sort"


def fetch_nav(q: str) -> dict:
    url = f"{BASE}?count=true&q={urllib.parse.quote(q, safe='()_.')}&inav={urllib.parse.quote(INAV)}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def get_manufacturers_from_response(data: dict, car_type: str = "Y") -> list:
    out = []
    nodes = (data.get("iNav") or {}).get("Nodes") or []
    for node in nodes:
        for facet in node.get("Facets") or []:
            if facet.get("Value") != car_type or facet.get("DisplayValue") != car_type:
                continue
            refs = (facet.get("Refinements") or {}).get("Nodes") or []
            for sub in refs:
                if sub.get("Name") == "Manufacturer":
                    for f in sub.get("Facets") or []:
                        val = f.get("DisplayValue") or f.get("Value") or ""
                        if not val:
                            continue
                        meta = f.get("Metadata") or {}
                        code = (meta.get("Code") or [None])[0]
                        eng = (meta.get("EngName") or [None])[0]
                        out.append({
                            "value": val,
                            "action": f.get("Action") or "",
                            "count": f.get("Count") or 0,
                            "code": code,
                            "name_en": eng,
                        })
                    return out
    return out


def _collect_facets_from_nodes(nodes: list, expression_contains: str) -> list:
    out = []
    for node in nodes:
        for f in node.get("Facets") or []:
            expr = f.get("Expression") or ""
            if expression_contains not in expr:
                refs = (f.get("Refinements") or {}).get("Nodes") or []
                out.extend(_collect_facets_from_nodes(refs, expression_contains))
                continue
            val = f.get("DisplayValue") or f.get("Value") or ""
            if not val:
                continue
            meta = f.get("Metadata") or {}
            code = (meta.get("Code") or [None])[0]
            eng = (meta.get("EngName") or [None])[0]
            out.append({
                "value": val,
                "action": f.get("Action") or "",
                "count": f.get("Count") or 0,
                "code": code,
                "name_en": eng,
            })
    return out


def get_facets_from_response(data: dict, facet_name: str) -> list:
    nodes = (data.get("iNav") or {}).get("Nodes") or []
    return _collect_facets_from_nodes(nodes, facet_name + ".")


def _row(source, brand, brand_en, model, model_en, generation, generation_en, type_val, type_en, trim_val, trim_en, count=None):
    name_en_parts = [p for p in [brand_en, model_en, generation_en, type_en, trim_en] if p]
    name_en_notes = " -> ".join(name_en_parts) if name_en_parts else ""
    return {
        "source": source,
        "brand": brand,
        "brand_en": brand_en or "",
        "model": model,
        "model_en": model_en or "",
        "generation": generation,
        "generation_en": generation_en or "",
        "body": "",
        "type": type_val or type_en,
        "type_en": (type_val or type_en) and (type_en or type_val or ""),
        "trim": trim_val or trim_en,
        "trim_en": trim_en or trim_val or "",
        "name_en_notes": name_en_notes,
        "count": count,
    }


def _collect_source_rows(source: str, q0: str, car_type: str, limit: int) -> list:
    rows = []
    try:
        data0 = fetch_nav(q0)
    except Exception as e:
        print("API error for %s: %s" % (source, e))
        return rows
    manufacturers = get_manufacturers_from_response(data0, car_type)
    if not manufacturers:
        return rows
    if limit:
        manufacturers = manufacturers[: limit]
    for mi, m in enumerate(manufacturers):
        brand = m["value"]
        brand_en = m.get("name_en") or ""
        action = m["action"]
        if not action:
            rows.append(_row(source, brand, brand_en, "", "", "", "", "", "", "", "", m.get("count")))
            continue
        print("  [%d/%d] %s" % (mi + 1, len(manufacturers), (brand_en or "brand" + str(mi + 1))), flush=True)
        time.sleep(0.15)
        try:
            data_m = fetch_nav(action)
        except Exception as e:
            print("  Error for", brand, ":", e)
            continue
        model_groups = get_facets_from_response(data_m, "ModelGroup")
        if not model_groups:
            rows.append(_row(source, brand, brand_en, "", "", "", "", "", "", "", "", m.get("count")))
            continue
        for mgi, mg in enumerate(model_groups):
            mg_name = mg["value"]
            mg_en = mg.get("name_en") or ""
            mg_action = mg.get("action") or ""
            if not mg_action:
                rows.append(_row(source, brand, brand_en, mg_name, mg_en, "", "", "", "", "", "", mg.get("count")))
                continue
            if (mgi + 1) % 10 == 0 or mgi == 0:
                print("    model_groups %d/%d" % (mgi + 1, len(model_groups)))
            time.sleep(0.15)
            try:
                data_mg = fetch_nav(mg_action)
            except Exception as e:
                print("  Error for", brand, mg_name, ":", e)
                rows.append(_row(source, brand, brand_en, mg_name, mg_en, "", "", "", "", "", "", mg.get("count")))
                continue
            models = get_facets_from_response(data_mg, "Model")
            if not models:
                rows.append(_row(source, brand, brand_en, mg_name, mg_en, "", "", "", "", "", "", mg.get("count")))
            for mo in models:
                gen = mo["value"]
                gen_en = mo.get("name_en") or ""
                mo_action = mo.get("action") or ""
                if not mo_action:
                    rows.append(_row(source, brand, brand_en, mg_name, mg_en, gen, gen_en, "", "", "", "", mo.get("count")))
                    continue
                time.sleep(0.15)
                try:
                    data_mo = fetch_nav(mo_action)
                except Exception as e:
                    rows.append(_row(source, brand, brand_en, mg_name, mg_en, gen, gen_en, "", "", "", "", mo.get("count")))
                    continue
                badge_groups = get_facets_from_response(data_mo, "BadgeGroup")
                if not badge_groups:
                    rows.append(_row(source, brand, brand_en, mg_name, mg_en, gen, gen_en, "", "", "", "", mo.get("count")))
                    continue
                for bg in badge_groups:
                    bg_action = bg.get("action") or ""
                    if not bg_action:
                        type_val = bg.get("value") or ""
                        type_en = bg.get("name_en") or type_val
                        rows.append(_row(source, brand, brand_en, mg_name, mg_en, gen, gen_en, type_val, type_en, "", "", bg.get("count")))
                        continue
                    time.sleep(0.1)
                    try:
                        data_bg = fetch_nav(bg_action)
                    except Exception:
                        type_val = bg.get("value") or ""
                        type_en = bg.get("name_en") or type_val
                        rows.append(_row(source, brand, brand_en, mg_name, mg_en, gen, gen_en, type_val, type_en, "", "", bg.get("count")))
                        continue
                    badges = get_facets_from_response(data_bg, "Badge")
                    if not badges:
                        type_val = bg.get("value") or ""
                        type_en = bg.get("name_en") or type_val
                        rows.append(_row(source, brand, brand_en, mg_name, mg_en, gen, gen_en, type_val, type_en, "", "", bg.get("count")))
                        continue
                    for badge in badges:
                        type_val = badge.get("value") or ""
                        type_en = badge.get("name_en") or type_val
                        b_action = badge.get("action") or ""
                        if not b_action:
                            rows.append(_row(source, brand, brand_en, mg_name, mg_en, gen, gen_en, type_val, type_en, "", "", badge.get("count")))
                            continue
                        time.sleep(0.1)
                        try:
                            data_b = fetch_nav(b_action)
                        except Exception:
                            rows.append(_row(source, brand, brand_en, mg_name, mg_en, gen, gen_en, type_val, type_en, "", "", badge.get("count")))
                            continue
                        badge_details = get_facets_from_response(data_b, "BadgeDetail")
                        if not badge_details:
                            rows.append(_row(source, brand, brand_en, mg_name, mg_en, gen, gen_en, type_val, type_en, "", "", badge.get("count")))
                            continue
                        for bd in badge_details:
                            trim_val = bd.get("value") or ""
                            trim_en = bd.get("name_en") or trim_val
                            rows.append(_row(source, brand, brand_en, mg_name, mg_en, gen, gen_en, type_val, type_en, trim_val, trim_en, bd.get("count")))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Limit to first N manufacturers per source (0 = all)")
    ap.add_argument("--no-import", action="store_true", help="Skip import cars (only domestic)")
    args = ap.parse_args()
    all_rows = []

    print("Fetching domestic manufacturers...", flush=True)
    q_domestic = "(And.Hidden.N._.CarType.Y.)"
    dom_rows = _collect_source_rows("domestic", q_domestic, "Y", args.limit)
    all_rows.extend(dom_rows)
    print("Domestic rows:", len(dom_rows), flush=True)

    if not args.no_import:
        print("Fetching import manufacturers...", flush=True)
        q_import = "(And.Hidden.N._.CarType.N.)"
        imp_rows = _collect_source_rows("import", q_import, "N", args.limit)
        all_rows.extend(imp_rows)
        print("Import rows:", len(imp_rows), flush=True)

    if not all_rows:
        print("No data collected.")
        return 1

    try:
        data0 = fetch_nav(q_domestic)
        with open(OUTPUT_DIR / "encar_api_raw_domestic.json", "w", encoding="utf-8") as f:
            json.dump(data0, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    csv_cols = ["source", "brand", "brand_en", "model", "model_en", "generation", "generation_en", "body", "type", "type_en", "trim", "trim_en", "name_en_notes", "count"]
    csv_path = OUTPUT_DIR / "encar_api_flat_for_mapping.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)
    print("Flat CSV saved:", csv_path, "(%d rows)" % len(all_rows), flush=True)

    tree = {"domestic": {"brands": []}, "import": {"brands": []}}
    for src in ("domestic", "import"):
        by_brand = {}
        for r in all_rows:
            if r["source"] != src:
                continue
            b = r["brand"]
            b_en = r.get("brand_en") or ""
            mg = r.get("model") or ""
            gen = r.get("generation") or ""
            t = r.get("type") or ""
            tr = r.get("trim") or ""
            if b not in by_brand:
                by_brand[b] = {"name": b, "name_en": b_en, "model_groups": {}}
            if not mg:
                continue
            if mg not in by_brand[b]["model_groups"]:
                by_brand[b]["model_groups"][mg] = []
            leaf = (gen + (" | " + t if t else "") + (" " + tr if tr else "")).strip() or gen
            if leaf and leaf not in by_brand[b]["model_groups"][mg]:
                by_brand[b]["model_groups"][mg].append(leaf)
        for b, bg in by_brand.items():
            tree[src]["brands"].append({
                "name": bg["name"],
                "name_en": bg.get("name_en") or "",
                "model_groups": [{"name": mg, "models": ms} for mg, ms in bg["model_groups"].items()],
            })
    tree_path = OUTPUT_DIR / "encar_api_tree.json"
    with open(tree_path, "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=2)
    print("Tree JSON saved:", tree_path, flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
