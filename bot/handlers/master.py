"""Хендлеры мастера: команда /reply_<id> и пересылка ответа клиенту.

Все хендлеры этого роутера защищены MasterOnlyMiddleware — сообщения от
посторонних пользователей сюда не попадают.
"""
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.states.order import MasterReply
from bot.database.repository import get_order, update_status
from bot.middlewares.master_only import MasterOnlyMiddleware

logger = logging.getLogger(__name__)

router = Router(name="master")
router.message.middleware(MasterOnlyMiddleware())


@router.message(Command(pattern=r"^reply_\d+$"))
async def cmd_reply(message: Message, state: FSMContext) -> None:
    """Мастер инициирует ответ клиенту командой /reply_<id>."""
    order_id = int(message.text.split("_", 1)[1])

    order = await get_order(order_id)
    if order is None:
        await message.answer(f"Заявка #{order_id} не найдена.")
        return

    await state.set_state(MasterReply.awaiting_text)
    await state.update_data(order_id=order_id, client_user_id=order.user_id)
    await message.answer(
        f"Пишите ответ клиенту по заявке #{order_id} "
        f"(устройство: {order.device_type}, телефон: {order.phone}):"
    )


@router.message(MasterReply.awaiting_text, F.text)
async def handle_master_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    order_id: int = data["order_id"]
    client_user_id: int = data["client_user_id"]

    try:
        await message.bot.send_message(
            chat_id=client_user_id,
            text=f"Ответ мастера по заявке #{order_id}:\n\n{message.text}",
        )
        await update_status(order_id, "in_progress")
        await message.answer(
            f"Ответ отправлен клиенту. Статус заявки #{order_id} → в работе."
        )
    except Exception:
        logger.exception("Не удалось отправить ответ клиенту по заявке #%s", order_id)
        await message.answer(
            "Не удалось отправить сообщение клиенту. "
            "Возможно, клиент заблокировал бота."
        )


@router.message(MasterReply.awaiting_text)
async def handle_master_reply_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте текстовый ответ для клиента.")
