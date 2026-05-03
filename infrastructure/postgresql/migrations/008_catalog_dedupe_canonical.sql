-- Слияние дублей листингов в Postgres (блок L): строка-дубликат указывает на канонический car_id.
-- psql "$DATABASE_URL" -f infrastructure/postgresql/migrations/008_catalog_dedupe_canonical.sql

ALTER TABLE cars ADD COLUMN IF NOT EXISTS dedupe_canonical_car_id TEXT NULL;

COMMENT ON COLUMN cars.dedupe_canonical_car_id IS
    'Если задано — этот листинг считается дублем канонической строки с данным car_id; '
    'не индексируется в Meilisearch; API отдаёт данные канонической карточки.';

CREATE INDEX IF NOT EXISTS idx_cars_dedupe_canonical_target
    ON cars (dedupe_canonical_car_id)
    WHERE dedupe_canonical_car_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cars_meili_source_rows
    ON cars (id ASC)
    WHERE dedupe_canonical_car_id IS NULL;
