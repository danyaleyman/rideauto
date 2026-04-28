-- auth + favorites migration (magic link)

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
