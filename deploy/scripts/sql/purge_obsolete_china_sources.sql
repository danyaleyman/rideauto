-- Однократно: удалить строки каталога со старым источником (до Che168 Global).
-- Условие сохраняет совместимость с историческими данными в БД.
-- Резервное копирование — на вашей стороне.
BEGIN;
DELETE FROM cars
WHERE lower(trim(source)) = 'dongchedi'
   OR car_id ILIKE 'dongchedi-%';
COMMIT;
