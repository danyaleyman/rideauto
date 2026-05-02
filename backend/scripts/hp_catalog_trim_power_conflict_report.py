#!/usr/bin/env python3
"""
Группы вида марка × модель × тип ДВС × объём × год, где указаны разные power_hp между разными norm_version.

Частый случай — разные комплектации законно отличаются по мощности: скрипт **не удаляет** строки,
а печатает сводку / CSV / HTML для ручной проверки.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from hp_catalog_store import (
    DEFAULT_DB_PATH,
    connect,
    ensure_llm_prompt_cache_schema,
    ensure_schema,
    family_conflict_canonical_key,
    verdict_bulk_get,
)


def _build_rows(conn, top: int) -> list[dict]:
    groups = conn.execute(
        """
        SELECT norm_manufacturer, norm_model, norm_engine_type,
               COALESCE(displacement_cc, -1) AS dcc,
               year_month,
               COUNT(*) AS cnt,
               COUNT(DISTINCT power_hp) AS d_hp
        FROM hp_catalog
        WHERE power_hp IS NOT NULL AND power_hp > 0 AND llm_status = 'done'
        GROUP BY norm_manufacturer, norm_model, norm_engine_type, COALESCE(displacement_cc, -1), year_month
        HAVING COUNT(DISTINCT power_hp) > 1
        ORDER BY cnt DESC
        LIMIT ?
        """,
        (max(1, min(top, 5000)),),
    ).fetchall()
    out_rows: list[dict] = []
    for nm, nmd, net, dcc, ym, _row_cnt, d_hp_gr in groups:
        detail = conn.execute(
            """
            SELECT id, norm_version, manufacturer, model, version, power_hp,
                   llm_confidence, source, llm_prompt_version
            FROM hp_catalog
            WHERE norm_manufacturer = ?
              AND norm_model = ?
              AND norm_engine_type = ?
              AND COALESCE(displacement_cc, -1) = ?
              AND year_month = ?
              AND power_hp IS NOT NULL AND power_hp > 0 AND llm_status = 'done'
            ORDER BY power_hp DESC, id ASC
            """,
            (nm, nmd, net, dcc, ym),
        ).fetchall()
        out_rows.append(
            {
                "key": {"nm": nm, "model": nmd, "engine": net, "dcc": dcc, "ym": ym},
                "distinct_hp_count": int(d_hp_gr),
                "variant_rows": len(detail),
                "variants": [
                    {
                        "id": int(r[0]),
                        "norm_version": r[1],
                        "manufacturer": r[2],
                        "model": r[3],
                        "version": r[4],
                        "power_hp": int(r[5]),
                        "confidence": r[6],
                        "source": r[7],
                        "prompt_ver": r[8],
                    }
                    for r in detail
                ],
            },
        )
    fkeys = [
        family_conflict_canonical_key(
            blk["key"]["nm"],
            blk["key"]["model"],
            blk["key"]["engine"],
            blk["key"]["dcc"],
            blk["key"]["ym"],
        )
        for blk in out_rows
    ]
    vmap = verdict_bulk_get(conn, fkeys)
    for blk, fk in zip(out_rows, fkeys):
        row = vmap.get(fk)
        if row is None:
            blk["operator_verdict"] = None
        else:
            blk["operator_verdict"] = {
                "verdict": str(row["verdict"] or ""),
                "notes": str(row["notes"] or ""),
                "operator": str(row["operator"] or ""),
                "updated_at": str(row["updated_at"] or ""),
            }
    return out_rows


def _write_csv(path: Path, families: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "family_key",
        "family_nm",
        "family_model",
        "family_engine",
        "family_cc",
        "family_ym",
        "operator_verdict",
        "operator_verdict_notes",
        "operator_verdict_author",
        "operator_verdict_updated",
        "row_id",
        "norm_version",
        "manufacturer",
        "model",
        "version",
        "power_hp",
        "llm_confidence",
        "source",
        "llm_prompt_version",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for blk in families:
            k = blk["key"]
            fk = family_conflict_canonical_key(k["nm"], k["model"], k["engine"], k["dcc"], k["ym"])
            ov = blk.get("operator_verdict") or {}
            for v in blk["variants"]:
                w.writerow(
                    {
                        "family_key": fk,
                        "family_nm": k["nm"],
                        "family_model": k["model"],
                        "family_engine": k["engine"],
                        "family_cc": k["dcc"],
                        "family_ym": k["ym"],
                        "operator_verdict": ov.get("verdict", ""),
                        "operator_verdict_notes": ov.get("notes", ""),
                        "operator_verdict_author": ov.get("operator", ""),
                        "operator_verdict_updated": ov.get("updated_at", ""),
                        "row_id": v["id"],
                        "norm_version": v["norm_version"],
                        "manufacturer": v["manufacturer"],
                        "model": v["model"],
                        "version": v["version"],
                        "power_hp": v["power_hp"],
                        "llm_confidence": v["confidence"],
                        "source": v["source"],
                        "llm_prompt_version": v["prompt_ver"],
                    }
                )


def _write_html(path: Path, families: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    parts = [
        "<!DOCTYPE html><html lang='ru'><meta charset='utf-8'/>",
        "<title>HP family conflicts</title>",
        "<style>table{border-collapse:collapse;}td,th{border:1px solid #ccc;padding:4px;}tr:nth-child(even){background:#f9f9f9;}</style>",
        "<body><h2>Разные hp в семействе блока × год</h2>",
        f"<p>Групп: {len(families)} — авто-merge не выполняется; проверять вручную. Вердикты оператора — из SQLite "
        f"(таблица hp_family_conflict_verdict), можно импортировать из CSV скриптом hp_family_verdict_import.py.</p>",
    ]
    for blk in families:
        k = blk["key"]
        fk = html.escape(family_conflict_canonical_key(k["nm"], k["model"], k["engine"], k["dcc"], k["ym"]))
        parts.append("<h4>")
        parts.append(html.escape(str(k)))
        parts.append("</h4>")
        parts.append(f"<p><small>family_key: {fk}</small></p>")
        ov = blk.get("operator_verdict")
        if ov and (ov.get("verdict") or ov.get("notes")):
            parts.append(
                "<p><strong>Вердикт оператора:</strong> "
                f"{html.escape(str(ov.get('verdict') or ''))} — "
                f"{html.escape(str(ov.get('notes') or ''))}"
                f" <small>({html.escape(str(ov.get('operator') or ''))}, {html.escape(str(ov.get('updated_at') or ''))})</small></p>"
            )
        else:
            parts.append("<p><em>Вердикт оператора не задан.</em></p>")
        parts.append("<table><tr><th>id</th><th>trim</th><th>hp</th><th>conf</th><th>src</th></tr>")
        for v in blk["variants"]:
            trim_s = html.escape(str(v.get("model") or "") + " · " + str(v.get("version") or ""))
            parts.append(
                "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                % (
                    v["id"],
                    trim_s,
                    v["power_hp"],
                    html.escape(str(v.get("confidence") or "")),
                    html.escape(str(v.get("source") or "")),
                )
            )
        parts.append("</table>")
    parts.append("</body></html>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="Отчёт: разные hp в одном семействе объёма/года")
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument("--json", action="store_true")
    p.add_argument("--top-groups", type=int, default=500, dest="top")
    p.add_argument("--csv", type=Path, default=None)
    p.add_argument("--html", type=Path, default=None)
    args = p.parse_args()

    conn = connect(args.db)
    ensure_schema(conn)
    ensure_llm_prompt_cache_schema(conn)
    try:
        out_rows = _build_rows(conn, args.top)
    finally:
        conn.close()

    summary = {"conflict_family_count": len(out_rows), "families": out_rows}
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"conflict_family_count={len(out_rows)} db={args.db}", flush=True)

    if args.csv:
        _write_csv(Path(args.csv), out_rows)
        print(f"csv written: {args.csv}", flush=True)
    if args.html:
        _write_html(Path(args.html), out_rows)
        print(f"html written: {args.html}", flush=True)

    if not args.json and not args.csv and not args.html:
        for blk in out_rows[:50]:
            k = blk["key"]
            print(
                f"--- nm={k['nm']} model={k['model']} eng={k['engine']} cc={k['dcc']} ym={k['ym']} variants={blk['variants']}",
                flush=True,
            )
        if len(out_rows) > 50:
            print("truncated console top 50; use --csv / --html / --json.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
