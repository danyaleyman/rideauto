-- B2C: сохранённые поиски каталога + email-уведомления о новых объявлениях

CREATE TABLE IF NOT EXISTS search_subscriptions (
    id               BIGSERIAL PRIMARY KEY,
    public_id        UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id          BIGINT NOT NULL REFERENCES auth_users (id) ON DELETE CASCADE,
    name             TEXT NOT NULL DEFAULT '',
    filters          JSONB NOT NULL DEFAULT '{}'::jsonb,
    query_string     TEXT NOT NULL DEFAULT '',
    market           TEXT NOT NULL DEFAULT 'korea',
    notify_enabled   BOOLEAN NOT NULL DEFAULT true,
    last_notified_at TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT search_subscriptions_public_id_uniq UNIQUE (public_id),
    CONSTRAINT search_subscriptions_market_chk CHECK (market IN ('korea', 'china'))
);

CREATE INDEX IF NOT EXISTS idx_search_subscriptions_user
    ON search_subscriptions (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_subscriptions_notify
    ON search_subscriptions (notify_enabled, updated_at)
    WHERE notify_enabled = true;
