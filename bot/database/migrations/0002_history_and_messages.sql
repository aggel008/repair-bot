-- История изменений статуса заявки (аудит).
CREATE TABLE IF NOT EXISTS order_status_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id),
    from_status TEXT,
    to_status   TEXT NOT NULL,
    actor       TEXT NOT NULL,            -- 'client' | 'master' | 'system'
    actor_id    INTEGER,
    note        TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_history_order ON order_status_history(order_id);

-- Переписка клиент↔мастер.
CREATE TABLE IF NOT EXISTS order_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id),
    direction   TEXT NOT NULL CHECK (direction IN ('client_to_master','master_to_client')),
    text        TEXT,
    voice_id    TEXT,
    photo_id    TEXT,
    tg_msg_id   INTEGER,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_order ON order_messages(order_id, created_at);

-- updated_at для orders + триггер автообновления.
ALTER TABLE orders ADD COLUMN updated_at DATETIME;
UPDATE orders SET updated_at = created_at;

CREATE TRIGGER IF NOT EXISTS orders_touch_updated
AFTER UPDATE ON orders FOR EACH ROW
WHEN OLD.updated_at IS NEW.updated_at  -- избегаем рекурсии
BEGIN
    UPDATE orders SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS orders_set_updated_on_insert
AFTER INSERT ON orders FOR EACH ROW
BEGIN
    UPDATE orders SET updated_at = NEW.created_at WHERE id = NEW.id;
END;
