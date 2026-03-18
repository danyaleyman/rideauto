# Encar production scraper

The script `encar_scraper.py` is a scalable, resumable replacement for the small-sample flow in `parser_full.py`. It is designed to collect up to ~200k listings from encar.com with:

- **Async I/O** (aiohttp): list pages are fetched sequentially; car details are fetched concurrently (configurable limit).
- **Checkpointing**: state is saved to SQLite (`scraper_checkpoint.db`): last list offset per car type, pending car IDs (with list item JSON), and collected IDs. On restart, the script resumes from the last checkpoint.
- **Storage**: results are written either to SQLite (`encar_cars.db`) or to chunked JSON files (e.g. `output_chunks/cars_00001.json`, 1000 cars per file).
- **Anti-blocking**: optional proxy list, User-Agent rotation, jitter between requests, exponential backoff and retries (429, 5xx), optional `Retry-After` respect.
- **Configuration**: all limits, delays, proxies, and paths are in `scraper_config.yaml`; overrides via env vars `SCRAPER_<section>_<key>` (e.g. `SCRAPER_HTTP_CONCURRENCY=10`).

## Quick start

1. Install dependencies: `pip install aiohttp PyYAML` (or use project `requirements.txt`).
2. Copy and edit config: `scraper_config.yaml`.
3. Run: `python encar_scraper.py`.

To resume after a stop, run the same command again; it will load pending IDs from the checkpoint and continue.

## Config overview

| Section    | Key examples | Description |
|-----------|--------------|-------------|
| `http`    | `concurrency`, `list_page_size`, `max_list_offset`, `list_page_delay_min/max`, `request_jitter_min/max`, `timeout_total` | Concurrency, pagination, delays, timeouts |
| `retry`   | `max_attempts`, `backoff_base`, `backoff_max`, `retry_statuses` | Retries and backoff |
| `proxy`   | `enabled`, `urls`, `rotate_every` | Proxy list and rotation |
| `user_agents` | List of strings | Rotated per request |
| `car_types`   | `["for", "kor"]` | Import / domestic |
| `checkpoint`  | `path`, `max_pending_ids`, `save_interval_seconds` | Checkpoint DB and limits |
| `storage`     | `backend` (sqlite / chunked_json), `sqlite.path`, `chunked_json.dir`, `cars_per_file`, `store_raw_responses` | Where and how to store cars |
| `logging`     | `level`, `file`, `console`, `format` | Log level and outputs |

## Pagination and offset limit

The list API uses `sr: "|ModifiedDate|{offset}|{limit}"`. If the API rejects large offsets (e.g. above 10,000), set `http.max_list_offset` in config. The script stops increasing offset when it gets an error or empty results. A future extension could add date-range or cursor-based strategies (e.g. filter by `ModifiedDate` day-by-day) if the API supports it; the checkpoint already stores the last offset per car type for resume.

## Output

- **SQLite**: table `cars` with `car_id`, `data_json` (full normalized car), optional `raw_json`, `created_at`. You can export to JSON or merge into your main DB later.
- **Chunked JSON**: each file is `{"result": [...], "meta": {"chunk": N}}` with the same structure as the original `cars.json` result array.

## Exports

To produce a single `cars.json` from the scraper’s SQLite DB for the existing frontend:

```python
import sqlite3, json
conn = sqlite3.connect("encar_cars.db")
rows = conn.execute("SELECT data_json FROM cars ORDER BY id").fetchall()
cars = [json.loads(r[0]) for r in rows]
# Normalize to { id, inner_id, change_type, created_at, data } if needed
with open("cars.json", "w", encoding="utf-8") as f:
    json.dump({"result": cars, "meta": {"limit": len(cars)}}, f, ensure_ascii=False, indent=2)
conn.close()
```

You can add a small script in the repo that runs this and optionally merges with `parser_full`’s `save_to_file` format.
