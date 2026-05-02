-- Полная очистка таблицы cars + связанные изображения + состояние чекпоинта Encar.
-- Без TRUNCATE чекпоинта парсер не начнёт «с начала»: id останутся в scraper_collected_ids.

\set ON_ERROR_STOP on

BEGIN;

TRUNCATE TABLE cars RESTART IDENTITY CASCADE;

TRUNCATE TABLE scraper_checkpoint_state;
TRUNCATE TABLE scraper_pending_ids;
TRUNCATE TABLE scraper_collected_ids;

COMMIT;

SELECT
  (SELECT COUNT(*) FROM cars) AS cars,
  (SELECT COUNT(*) FROM car_images) AS car_images,
  (SELECT COUNT(*) FROM scraper_pending_ids) AS checkpoint_pending,
  (SELECT COUNT(*) FROM scraper_collected_ids) AS checkpoint_collected;
