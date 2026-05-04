-- China (Che168 Global): отдельные флаги листинга. Колонки Dongchedi удалены.
-- Перед применением на проде: при необходимости сохраните/удалите строки
-- (см. deploy/scripts/sql/purge_obsolete_china_sources.sql).

DROP INDEX IF EXISTS idx_cars_dongchedi_listing_checker;

ALTER TABLE cars DROP COLUMN IF EXISTS dongchedi_listing_sold;
ALTER TABLE cars DROP COLUMN IF EXISTS dongchedi_listing_checked_at;

ALTER TABLE cars ADD COLUMN IF NOT EXISTS che168_listing_sold BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS che168_listing_checked_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_cars_che168_listing_checker
    ON cars (che168_listing_checked_at NULLS FIRST)
    WHERE source = 'che168';

COMMENT ON COLUMN cars.che168_listing_sold IS
    'Лот снят с публикации на Che168 Global (live checker / ручная пометка)';
COMMENT ON COLUMN cars.che168_listing_checked_at IS
    'Время последней проверки доступности лота на стороне Che168';
