-- Esquema SYNTHLAB. Todas las consultas de la app son parametrizadas.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY,
    email           TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    name            TEXT    NOT NULL,
    password_hash   TEXT    NOT NULL,
    role            TEXT    NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    email_verified  INTEGER NOT NULL DEFAULT 0,
    failed_logins   INTEGER NOT NULL DEFAULT 0,
    locked_until    INTEGER,
    disabled        INTEGER NOT NULL DEFAULT 0,
    totp_secret     TEXT,
    totp_pending    TEXT,
    totp_last_step  INTEGER,
    created_at      INTEGER NOT NULL,
    updated_at      INTEGER NOT NULL,
    last_login_at   INTEGER,
    password_changed_at INTEGER NOT NULL
);

-- Sesiones de servidor: la cookie sólo lleva un token aleatorio; aquí guardamos su SHA-256.
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT    NOT NULL UNIQUE,
    created_at  INTEGER NOT NULL,
    last_seen   INTEGER NOT NULL,
    ip          TEXT,
    user_agent  TEXT
);
CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions(user_id);

-- Tokens de un solo uso (verificación, reset). Sólo se guarda el hash.
CREATE TABLE IF NOT EXISTS tokens (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose     TEXT    NOT NULL CHECK (purpose IN ('verify', 'reset')),
    token_hash  TEXT    NOT NULL UNIQUE,
    expires_at  INTEGER NOT NULL,
    used_at     INTEGER
);

CREATE TABLE IF NOT EXISTS recovery_codes (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_hash   TEXT    NOT NULL,
    used_at     INTEGER
);

CREATE TABLE IF NOT EXISTS patterns (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    bpm         INTEGER NOT NULL,
    steps       TEXT    NOT NULL,           -- JSON 4x16 de 0/1, validado
    share_slug  TEXT    UNIQUE,             -- NULL = privado
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_patterns_user ON patterns(user_id);

CREATE TABLE IF NOT EXISTS favorites (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product     TEXT    NOT NULL,
    created_at  INTEGER NOT NULL,
    PRIMARY KEY (user_id, product)
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    email       TEXT    NOT NULL,
    body        TEXT    NOT NULL,
    ip          TEXT,
    created_at  INTEGER NOT NULL,
    handled     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS newsletter (
    id          INTEGER PRIMARY KEY,
    email       TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    token_hash  TEXT    NOT NULL,
    confirmed   INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS rate_limits (
    key         TEXT    PRIMARY KEY,
    window_start INTEGER NOT NULL,
    hits        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY,
    ts          INTEGER NOT NULL,
    event       TEXT    NOT NULL,
    user_id     INTEGER,
    user_label  TEXT,
    ip          TEXT,
    method      TEXT,
    path        TEXT,
    status      INTEGER,
    detail      TEXT
);
CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit_log(ts);
