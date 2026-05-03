-- PostgreSQL catalog schema (normalized from historical cars source).
-- Target: FastAPI + btree filters aligned with каталогом / Meilisearch
-- Requires: PostgreSQL 12+ (GENERATED STORED columns)
-- Optional (superuser / rds_superuser): CREATE EXTENSION pg_trgm;
--   + GIN (mark gin_trgm_ops) for fuzzy search — not required for catalog filters.

-- -----------------------------------------------------------------------------
-- Reference: brands / models (facet strings from JSON `data.mark` / `data.model`)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS brands (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    name_norm   TEXT GENERATED ALWAYS AS (lower(trim(name))) STORED,
    CONSTRAINT brands_name_norm_uniq UNIQUE (name_norm)
);

CREATE TABLE IF NOT EXISTS models (
    id          BIGSERIAL PRIMARY KEY,
    brand_id    BIGINT NOT NULL REFERENCES brands (id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    name_norm   TEXT GENERATED ALWAYS AS (lower(trim(name))) STORED,
    CONSTRAINT models_brand_name_uniq UNIQUE (brand_id, name_norm)
);

-- -----------------------------------------------------------------------------
-- cars: transactional source of truth; denormalized columns mirror catalog filters
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cars (
    id                       BIGSERIAL PRIMARY KEY,
    car_id                   TEXT NOT NULL,
    brand_id                 BIGINT REFERENCES brands (id) ON DELETE SET NULL,
    model_id                 BIGINT REFERENCES models (id) ON DELETE SET NULL,
    -- Original display strings (facets use the same values as today)
    mark                     TEXT,
    model                    TEXT,
    generation               TEXT,
    trim_name                TEXT,
    encar_model_group        TEXT,
    body_type                TEXT,
    fuel_type                TEXT,
    transmission_type        TEXT,
    drive_type               TEXT,
    color                    TEXT,
    source                   TEXT NOT NULL DEFAULT 'encar',
    listing_partition_key    TEXT NOT NULL,
    power_hp                 INTEGER,
    power_kw                 INTEGER,
    torque_nm                INTEGER,
    displacement_cc          INTEGER,
    displacement_label       TEXT,
    price_rub                DOUBLE PRECISION,
    mileage_km               INTEGER,
    year                     INTEGER,
    year_month               INTEGER,
    insurance_cases          INTEGER NOT NULL DEFAULT 0,
    insurance_payout_krw     DOUBLE PRECISION NOT NULL DEFAULT 0,
    insurance_payout_rub     DOUBLE PRECISION,
    damaged_parts_count      INTEGER NOT NULL DEFAULT 0,
    offer_created_at         TIMESTAMPTZ,
    -- Дневной encar_listing_live_checker: снято с продажи на Encar до ночной выгрузки
    encar_listing_sold       BOOLEAN NOT NULL DEFAULT false,
    encar_listing_checked_at TIMESTAMPTZ,
    -- Дневной dongchedi_listing_live_checker: снято с продажи на Dongchedi до ночной выгрузки
    dongchedi_listing_sold       BOOLEAN NOT NULL DEFAULT false,
    dongchedi_listing_checked_at TIMESTAMPTZ,
    data                     JSONB NOT NULL,
    raw                      JSONB,
    source_internal_id       BIGINT,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    dedupe_canonical_car_id  TEXT NULL,
    CONSTRAINT cars_car_id_unique UNIQUE (car_id)
);

COMMENT ON COLUMN cars.listing_partition_key IS
    'Dedup key: COALESCE(inner_id, data.id, car_id) — listing partition для каталога';
COMMENT ON COLUMN cars.year_month IS
    'Ordinal month index: year*12 + (month-1), matching ym_from / ym_to in catalog.js';
COMMENT ON COLUMN cars.dedupe_canonical_car_id IS
    'Дубль листинга → car_id канонической строки; см. migrations/008_catalog_dedupe_canonical.sql';

-- -----------------------------------------------------------------------------
-- images: normalized from data.images (list or JSON string of URLs)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS car_images (
    id          BIGSERIAL PRIMARY KEY,
    car_pk      BIGINT NOT NULL REFERENCES cars (id) ON DELETE CASCADE,
    url         TEXT NOT NULL,
    sort_order  SMALLINT NOT NULL DEFAULT 0,
    is_primary  BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT car_images_car_url_uniq UNIQUE (car_pk, url)
);

-- -----------------------------------------------------------------------------
-- Indexes — фильтры каталога (фасеты / совместимость с query API)
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_cars_brand_id ON cars (brand_id);
CREATE INDEX IF NOT EXISTS idx_cars_model_id ON cars (model_id);
CREATE INDEX IF NOT EXISTS idx_cars_mark ON cars (mark);
CREATE INDEX IF NOT EXISTS idx_cars_model ON cars (model);
CREATE INDEX IF NOT EXISTS idx_cars_mark_model ON cars (mark, model);

CREATE INDEX IF NOT EXISTS idx_cars_price ON cars (price_rub);
CREATE INDEX IF NOT EXISTS idx_cars_mileage ON cars (mileage_km);
CREATE INDEX IF NOT EXISTS idx_cars_year ON cars (year);
CREATE INDEX IF NOT EXISTS idx_cars_year_month ON cars (year_month);

CREATE INDEX IF NOT EXISTS idx_cars_body ON cars (body_type);
CREATE INDEX IF NOT EXISTS idx_cars_fuel ON cars (fuel_type);
CREATE INDEX IF NOT EXISTS idx_cars_trans ON cars (transmission_type);
CREATE INDEX IF NOT EXISTS idx_cars_color ON cars (color);
CREATE INDEX IF NOT EXISTS idx_cars_drive ON cars (drive_type);

CREATE INDEX IF NOT EXISTS idx_cars_generation ON cars (generation);
CREATE INDEX IF NOT EXISTS idx_cars_trim ON cars (trim_name);
CREATE INDEX IF NOT EXISTS idx_cars_encar_model_group ON cars (encar_model_group);

CREATE INDEX IF NOT EXISTS idx_cars_power ON cars (power_hp);
CREATE INDEX IF NOT EXISTS idx_cars_power_kw ON cars (power_kw);
CREATE INDEX IF NOT EXISTS idx_cars_torque ON cars (torque_nm);
CREATE INDEX IF NOT EXISTS idx_cars_displacement ON cars (displacement_cc);
CREATE INDEX IF NOT EXISTS idx_cars_displacement_label ON cars (displacement_label);

CREATE INDEX IF NOT EXISTS idx_cars_source ON cars (source);
CREATE INDEX IF NOT EXISTS idx_cars_source_brand_model ON cars (source, brand_id, model_id);

CREATE INDEX IF NOT EXISTS idx_cars_ins_cases ON cars (insurance_cases);
CREATE INDEX IF NOT EXISTS idx_cars_ins_payout_rub ON cars (insurance_payout_rub);
CREATE INDEX IF NOT EXISTS idx_cars_damaged ON cars (damaged_parts_count);

CREATE INDEX IF NOT EXISTS idx_cars_listing_partition ON cars (listing_partition_key, id DESC);
CREATE INDEX IF NOT EXISTS idx_cars_offer_created ON cars (offer_created_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_cars_encar_listing_checker
    ON cars (encar_listing_checked_at NULLS FIRST)
    WHERE (source IS NULL OR source = 'encar')
      AND car_id NOT LIKE 'dongchedi-%';

CREATE INDEX IF NOT EXISTS idx_cars_dongchedi_listing_checker
    ON cars (dongchedi_listing_checked_at NULLS FIRST)
    WHERE source = 'dongchedi';

CREATE INDEX IF NOT EXISTS idx_cars_data_gin ON cars USING GIN (data);

CREATE INDEX IF NOT EXISTS idx_cars_dedupe_canonical_target
    ON cars (dedupe_canonical_car_id)
    WHERE dedupe_canonical_car_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cars_meili_source_rows
    ON cars (id ASC)
    WHERE dedupe_canonical_car_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_car_images_car_sort ON car_images (car_pk, sort_order);

-- -----------------------------------------------------------------------------
-- scraper checkpoint (Encar list/pending/collected state)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS scraper_checkpoint_state (
    scope TEXT NOT NULL DEFAULT 'encar',
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (scope, key)
);

CREATE TABLE IF NOT EXISTS scraper_pending_ids (
    scope TEXT NOT NULL DEFAULT 'encar',
    car_id TEXT NOT NULL,
    car_type TEXT NOT NULL,
    item_json TEXT,
    added_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (scope, car_id)
);

CREATE INDEX IF NOT EXISTS idx_scraper_pending_added
    ON scraper_pending_ids (scope, added_at);

CREATE TABLE IF NOT EXISTS scraper_collected_ids (
    scope TEXT NOT NULL DEFAULT 'encar',
    car_id TEXT NOT NULL,
    PRIMARY KEY (scope, car_id)
);

-- -----------------------------------------------------------------------------
-- auth: email magic link users/sessions + user favorites
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS auth_users (
    id            BIGSERIAL PRIMARY KEY,
    email         TEXT NOT NULL,
    email_norm    TEXT GENERATED ALWAYS AS (lower(trim(email))) STORED,
    is_active     BOOLEAN NOT NULL DEFAULT true,
    last_login_at TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT auth_users_email_norm_uniq UNIQUE (email_norm)
);

CREATE TABLE IF NOT EXISTS auth_magic_tokens (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES auth_users (id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    ip          TEXT,
    ua          TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT auth_magic_tokens_hash_uniq UNIQUE (token_hash)
);

CREATE INDEX IF NOT EXISTS idx_auth_magic_tokens_user ON auth_magic_tokens (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_auth_magic_tokens_exp ON auth_magic_tokens (expires_at);
CREATE INDEX IF NOT EXISTS idx_auth_magic_tokens_open ON auth_magic_tokens (used_at, expires_at);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id            BIGSERIAL PRIMARY KEY,
    user_id        BIGINT NOT NULL REFERENCES auth_users (id) ON DELETE CASCADE,
    session_hash   TEXT NOT NULL,
    expires_at     TIMESTAMPTZ NOT NULL,
    revoked_at     TIMESTAMPTZ,
    ip             TEXT,
    ua             TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at   TIMESTAMPTZ,
    CONSTRAINT auth_sessions_hash_uniq UNIQUE (session_hash)
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_open ON auth_sessions (revoked_at, expires_at);

CREATE TABLE IF NOT EXISTS user_favorites (
    user_id     BIGINT NOT NULL REFERENCES auth_users (id) ON DELETE CASCADE,
    car_id      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, car_id)
);

CREATE INDEX IF NOT EXISTS idx_user_favorites_car ON user_favorites (car_id);

