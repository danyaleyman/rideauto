-- B2C: persistence заявок с сайта (дублирует email, даёт историю для CRM-lite)

CREATE TABLE IF NOT EXISTS lead_requests (
    id              BIGSERIAL PRIMARY KEY,
    full_name       TEXT NOT NULL,
    contact_method  TEXT NOT NULL,
    message         TEXT NOT NULL,
    pd_agree        BOOLEAN NOT NULL DEFAULT true,
    ip              TEXT,
    ua              TEXT,
    email_sent      BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lead_requests_created ON lead_requests (created_at DESC);
