import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import BOT_TOKEN, MASTER_CHAT_ID
from bot.database.db import init_db
from bot.handlers import client, master, common
from bot.middlewares.throttling import ThrottlingMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _startup_check(bot: Bot) -> None:
    """Проверка конфигурации до начала polling.

    Если MASTER_CHAT_ID невалиден или бот не имеет доступа к чату —
    падаем громко на старте, а не молча в момент первой заявки.
    """
    me = await bot.get_me()
    logger.info("Бот: @%s (id=%s)", me.username, me.id)

    try:
        chat = await bot.get_chat(MASTER_CHAT_ID)
        logger.info("Чат мастера: %s (id=%s)", chat.title or chat.full_name, chat.id)
    except TelegramAPIError as e:
        logger.error(
            "Не удалось получить чат мастера (MASTER_CHAT_ID=%s): %s. "
            "Убедитесь, что мастер отправил боту /start или бот добавлен в группу.",
            MASTER_CHAT_ID, e,
        )
        # Не падаем — бот всё равно может работать, заявки будут сохраняться


async def main() -> None:
    await init_db()
    logger.info("База данных инициализирована")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Throttling: глобально на все сообщения, чтобы спам не выводил бота из строя
    dp.message.middleware(ThrottlingMiddleware(rate_limit=0.5))

    # Порядок: common (cancel/help) → master → client (fallback в конце)
    dp.include_router(common.router)
    dp.include_router(master.router)
    dp.include_router(client.router)

    # Глобальный обработчик ошибок
    dp.errors.register(common.on_error)

    await _startup_check(bot)
    logger.info("Бот запускается...")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
