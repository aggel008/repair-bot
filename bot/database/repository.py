"""Репозиторий заявок и связанных сущностей.

Тонкий слой поверх aiosqlite — без бизнес-логики. Бизнес-логика (например,
«при смене статуса записать в audit») живёт в services/order_service.py.
"""
from dataclasses import dataclass
from typing import Optional

import aiosqlite

from bot.config import DATABASE_PATH
from bot.domain.enums import CLOSED_STATUSES, OrderStatus


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
    updated_at: Optional[str] = None              # появилось в миграции 0002
    device_model: Optional[str] = None            # появилось в миграции 0004
    notification_message_id: Optional[int] = None # появилось в миграции 0004
    topic_id: Optional[int] = None                # появилось в миграции 0005


def _row_to_order(row: aiosqlite.Row) -> Order:
    """Безопасное преобразование строки БД в Order, игнорирует лишние колонки."""
    keys = set(row.keys())
    fields = {k: row[k] for k in keys if k in Order.__dataclass_fields__}
    return Order(**fields)


# --- Заявки ---

async def create_order(
    user_id: int,
    username: Optional[str],
    device_type: str,
    device_model: Optional[str],
    problem: str,
    phone: str,
    voice_id: Optional[str] = None,
) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO orders
                (user_id, username, device_type, device_model, problem, voice_id, phone)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, device_type, device_model, problem, voice_id, phone),
        )
        order_id = cursor.lastrowid
        await db.execute(
            """
            INSERT INTO order_status_history (order_id, from_status, to_status, actor, actor_id)
            VALUES (?, NULL, ?, 'client', ?)
            """,
            (order_id, OrderStatus.NEW.value, user_id),
        )
        await db.commit()
        return order_id


async def set_notification_message_id(order_id: int, message_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE orders SET notification_message_id = ? WHERE id = ?",
            (message_id, order_id),
        )
        await db.commit()


async def set_topic_id(order_id: int, topic_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE orders SET topic_id = ? WHERE id = ?",
            (topic_id, order_id),
        )
        await db.commit()


async def get_order_by_topic_id(topic_id: int) -> Optional[Order]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM orders WHERE topic_id = ? LIMIT 1", (topic_id,)
        )
        row = await cursor.fetchone()
        return _row_to_order(row) if row else None


async def get_order_by_notification_msg(message_id: int) -> Optional[Order]:
    """Найти заявку по message_id её корневого уведомления у мастера.

    Используется, когда мастер свайп-реплаит на старое уведомление.
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM orders WHERE notification_message_id = ? LIMIT 1",
            (message_id,),
        )
        row = await cursor.fetchone()
        return _row_to_order(row) if row else None


async def find_recent_duplicate(
    user_id: int, device_type: str, problem: str, phone: str, window_sec: int = 60
) -> Optional[int]:
    """Ищет недавнюю идентичную заявку клиента — защита от двойного клика «Подтвердить»."""
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
        return _row_to_order(row) if row else None


async def update_status(
    order_id: int,
    status: str,
    actor: str = "system",
    actor_id: Optional[int] = None,
    note: Optional[str] = None,
) -> None:
    """Меняет статус и пишет запись в order_status_history атомарно."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT status FROM orders WHERE id = ?", (order_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return
        from_status = row[0]
        if from_status == status:
            return

        await db.execute(
            "UPDATE orders SET status = ? WHERE id = ?", (status, order_id)
        )
        await db.execute(
            """
            INSERT INTO order_status_history
                (order_id, from_status, to_status, actor, actor_id, note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (order_id, from_status, status, actor, actor_id, note),
        )
        await db.commit()


async def get_latest_open_order_by_user(user_id: int) -> Optional[Order]:
    """Последняя заявка клиента, которая ещё не закрыта/не отменена."""
    closed = ",".join(f"'{s.value}'" for s in CLOSED_STATUSES)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT * FROM orders
            WHERE user_id = ? AND status NOT IN ({closed})
            ORDER BY id DESC LIMIT 1
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        return _row_to_order(row) if row else None


async def list_open_orders(limit: int = 20) -> list[Order]:
    """Список открытых заявок (для /orders мастера)."""
    closed = ",".join(f"'{s.value}'" for s in CLOSED_STATUSES)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT * FROM orders
            WHERE status NOT IN ({closed})
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        return [_row_to_order(r) for r in rows]


async def list_user_orders(user_id: int, limit: int = 10) -> list[Order]:
    """Заявки клиента (для /myorders)."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [_row_to_order(r) for r in rows]


# --- Сообщения переписки ---

async def add_order_photo(order_id: int, file_id: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO order_photos (order_id, file_id) VALUES (?, ?)",
            (order_id, file_id),
        )
        await db.commit()


async def get_order_photos(order_id: int) -> list[str]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT file_id FROM order_photos WHERE order_id = ? ORDER BY id",
            (order_id,),
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def log_message(
    order_id: int,
    direction: str,  # 'client_to_master' | 'master_to_client'
    text: Optional[str] = None,
    voice_id: Optional[str] = None,
    photo_id: Optional[str] = None,
    tg_msg_id: Optional[int] = None,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO order_messages (order_id, direction, text, voice_id, photo_id, tg_msg_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (order_id, direction, text, voice_id, photo_id, tg_msg_id),
        )
        await db.commit()
