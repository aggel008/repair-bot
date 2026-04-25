from dataclasses import dataclass
from typing import Optional
import aiosqlite
from bot.config import DATABASE_PATH


@dataclass
class Order:
    id: int
    user_id: int
    username: Optional[str]
    device_type: str
    problem: str
    voice_id: Optional[str]
    phone: str
    status: str
    created_at: str


async def create_order(
    user_id: int,
    username: Optional[str],
    device_type: str,
    problem: str,
    phone: str,
    voice_id: Optional[str] = None,
) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO orders (user_id, username, device_type, problem, voice_id, phone)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, device_type, problem, voice_id, phone),
        )
        await db.commit()
        return cursor.lastrowid


async def find_recent_duplicate(
    user_id: int, device_type: str, problem: str, phone: str, window_sec: int = 60
) -> Optional[int]:
    """Ищет недавнюю идентичную заявку клиента — защита от двойного клика «Подтвердить».

    Возвращает id заявки или None.
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            f"""
            SELECT id FROM orders
            WHERE user_id = ? AND device_type = ? AND problem = ? AND phone = ?
              AND created_at >= datetime('now', '-{int(window_sec)} seconds')
            ORDER BY id DESC LIMIT 1
            """,
            (user_id, device_type, problem, phone),
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def get_order(order_id: int) -> Optional[Order]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return Order(**dict(row))


async def update_status(order_id: int, status: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE orders SET status = ? WHERE id = ?", (status, order_id)
        )
        await db.commit()


async def get_latest_open_order_by_user(user_id: int) -> Optional[Order]:
    """Последняя заявка клиента, которая ещё не закрыта/не отменена."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM orders
            WHERE user_id = ? AND status NOT IN ('done', 'cancelled')
            ORDER BY id DESC LIMIT 1
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return Order(**dict(row))
