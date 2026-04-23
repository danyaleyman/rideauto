ALTER TABLE cars
    ADD COLUMN IF NOT EXISTS dongchedi_listing_sold BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS dongchedi_listing_checked_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_cars_dongchedi_listing_checker
    ON cars (dongchedi_listing_checked_at NULLS FIRST)
    WHERE source = 'dongchedi';

