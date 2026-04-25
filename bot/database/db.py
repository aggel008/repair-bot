"""Инициализация БД и применение миграций.

Версионирование схемы через PRAGMA user_version. Каждый файл в migrations/
содержит SQL для перехода на следующую версию.
"""
import logging
from pathlib import Path

import aiosqlite

from bot.config import DATABASE_PATH

logger = logging.getLogger(__name__)
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def _current_version(db: aiosqlite.Connection) -> int:
    cursor = await db.execute("PRAGMA user_version")
    row = await cursor.fetchone()
    return int(row[0]) if row else 0


async def _set_version(db: aiosqlite.Connection, version: int) -> None:
    # PRAGMA не поддерживает параметризацию — версия проверена как int выше
    await db.execute(f"PRAGMA user_version = {int(version)}")


async def init_db() -> None:
    """Применяет все недостающие миграции по порядку. Идемпотентно."""
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        logger.warning("Не найдено ни одной миграции в %s", MIGRATIONS_DIR)
        return

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Включаем foreign keys (по умолчанию выключены в SQLite)
        await db.execute("PRAGMA foreign_keys = ON")

        current = await _current_version(db)
        for file in files:
            # Имя файла: NNNN_description.sql
            try:
                version = int(file.stem.split("_", 1)[0])
            except ValueError:
                logger.error("Неверное имя миграции: %s — пропускаем", file.name)
                continue

            if version <= current:
                continue

            logger.info("Применяю миграцию %s", file.name)
            sql = file.read_text(encoding="utf-8")
            await db.executescript(sql)
            await _set_version(db, version)
            await db.commit()

        final = await _current_version(db)
        logger.info("Схема БД на версии %s", final)
