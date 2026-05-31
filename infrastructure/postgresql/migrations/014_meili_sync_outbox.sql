-- PG → Meili: outbox для инкрементальной индексации (B2C каталог)

CREATE TABLE IF NOT EXISTS meili_sync_outbox (
    id           BIGSERIAL PRIMARY KEY,
    car_id       TEXT NOT NULL,
    op           TEXT NOT NULL DEFAULT 'upsert',
    enqueued_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ,
    CONSTRAINT meili_sync_outbox_op_chk CHECK (op IN ('upsert', 'delete'))
);

CREATE INDEX IF NOT EXISTS idx_meili_outbox_pending
    ON meili_sync_outbox (enqueued_at)
    WHERE processed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_meili_outbox_car_pending
    ON meili_sync_outbox (car_id)
    WHERE processed_at IS NULL;

CREATE OR REPLACE FUNCTION trg_cars_meili_outbox_enqueue() RETURNS trigger AS $$
BEGIN
    DELETE FROM meili_sync_outbox
    WHERE car_id = NEW.car_id AND processed_at IS NULL;
    INSERT INTO meili_sync_outbox (car_id, op)
    VALUES (NEW.car_id, 'upsert');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS cars_meili_outbox_trg ON cars;
CREATE TRIGGER cars_meili_outbox_trg
    AFTER INSERT OR UPDATE ON cars
    FOR EACH ROW
    EXECUTE FUNCTION trg_cars_meili_outbox_enqueue();
