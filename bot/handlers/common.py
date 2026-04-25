"""Общие хендлеры: /cancel, /help, глобальный обработчик ошибок."""
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ErrorEvent

from bot.keyboards.builder import remove_keyboard

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Глобальная отмена — выход из любого FSM-состояния."""
    current = await state.get_state()
    await state.clear()
    if current is None:
        await message.answer("Сейчас отменять нечего. Чтобы создать заявку — /start")
    else:
        await message.answer(
            "Действие отменено. Чтобы начать заново — /start",
            reply_markup=remove_keyboard(),
        )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Я помогу оставить заявку на ремонт техники.\n\n"
        "Команды:\n"
        "/start — новая заявка\n"
        "/myorders — мои заявки\n"
        "/cancel — отменить текущий шаг\n"
        "/help — это сообщение"
    )


async def on_error(event: ErrorEvent) -> bool:
    """Глобальный обработчик исключений в хендлерах."""
    logger.exception(
        "Необработанная ошибка при обработке апдейта: %s",
        event.exception,
    )
    # Пытаемся вежливо ответить пользователю, если есть message
    update = event.update
    if update.message is not None:
        try:
            await update.message.answer(
                "Что-то пошло не так. Попробуйте /start или /cancel."
            )
        except Exception:
            pass
    return True
