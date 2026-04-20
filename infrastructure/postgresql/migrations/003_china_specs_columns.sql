ALTER TABLE cars
    ADD COLUMN IF NOT EXISTS power_kw INTEGER,
    ADD COLUMN IF NOT EXISTS torque_nm INTEGER,
    ADD COLUMN IF NOT EXISTS displacement_label TEXT;

CREATE INDEX IF NOT EXISTS idx_cars_power_kw ON cars (power_kw);
CREATE INDEX IF NOT EXISTS idx_cars_torque ON cars (torque_nm);
CREATE INDEX IF NOT EXISTS idx_cars_displacement_label ON cars (displacement_label);
