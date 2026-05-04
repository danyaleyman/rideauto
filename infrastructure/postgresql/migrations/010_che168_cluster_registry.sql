-- Реестр кластеров Che168: склейка лотов между прогонами (cluster_id / VIN).
-- psql "$DATABASE_URL" -f infrastructure/postgresql/migrations/010_che168_cluster_registry.sql

CREATE TABLE IF NOT EXISTS che168_cluster_registry (
    cluster_key TEXT NOT NULL,
    car_id      TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (cluster_key, car_id)
);

CREATE INDEX IF NOT EXISTS idx_che168_cluster_registry_car
    ON che168_cluster_registry (car_id);

COMMENT ON TABLE che168_cluster_registry IS
    'Участники кластера листингов Che168; cars.dedupe_canonical_car_id выставляется при сохранении.';
