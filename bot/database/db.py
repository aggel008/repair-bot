import aiosqlite
from bot.config import DATABASE_PATH


async def init_db() -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
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
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)"
        )
        await db.commit()
