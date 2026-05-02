-- Encar category.modelGroupName → denormalized column for facets / Meilisearch model_group
ALTER TABLE cars
    ADD COLUMN IF NOT EXISTS encar_model_group TEXT;

CREATE INDEX IF NOT EXISTS idx_cars_encar_model_group ON cars (encar_model_group);

COMMENT ON COLUMN cars.encar_model_group IS
    'Encar listing modelGroupName (линейка/поколение в каталоге Encar); NULL для не‑Encar.';
