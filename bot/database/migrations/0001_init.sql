CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    username    TEXT,
    device_type TEXT NOT NULL,
    problem     TEXT NOT NULL,
    voice_id    TEXT,
    phone       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'new',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status  ON orders(status);
