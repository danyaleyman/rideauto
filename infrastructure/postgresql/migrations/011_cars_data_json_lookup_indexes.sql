-- Btree indexes for fetch_car_any_id JSON fallbacks (fastapi_app.pg_catalog._fetch_row_by_json_ref_fields).
-- Equality on jsonb text paths without an index can seq-scan `cars` until asyncpg command_timeout.
-- psql "$DATABASE_URL" -f infrastructure/postgresql/migrations/011_cars_data_json_lookup_indexes.sql

CREATE INDEX IF NOT EXISTS idx_cars_data_json_text_id
    ON cars ((data->>'id'), id DESC);

CREATE INDEX IF NOT EXISTS idx_cars_data_json_inner_id
    ON cars ((data->>'inner_id'), id DESC);

CREATE INDEX IF NOT EXISTS idx_cars_data_json_nested_inner_id
    ON cars ((data->'data'->>'inner_id'), id DESC);
