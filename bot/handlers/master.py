from typing import Optional
from aiogram import Router, Bot, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.config import MASTER_CHAT_ID
from bot.states.order import MasterReply
from bot.database.repository import get_order, update_status
from bot.keyboards.builder import remove_keyboard

router = Router()


async def notify_master(
    bot: Bot,
    order_id: int,
    device_label: str,
    problem: str,
    voice_id: Optional[str],
    phone: str,
    user_id: int,
    username: Optional[str],
) -> None:
    client_ref = f"@{username}" if username else f"ID {user_id}"
    voice_note = "\n🎤 Есть голосовое сообщение (см. file_id в БД)" if voice_id else ""

    text = (
        f"📋 Новая заявка #{order_id}\n\n"
        f"Устройство: {device_label}\n"
        f"Проблема: {problem}{voice_note}\n"
        f"Телефон: {phone}\n"
        f"Клиент: {client_ref}\n\n"
        f"Ответить клиенту: /reply_{order_id}"
    )
    await bot.send_message(chat_id=MASTER_CHAT_ID, text=text)


# Команда /reply_<id> — мастер инициирует ответ клиенту
@router.message(Command(pattern=r"^reply_\d+$"))
async def cmd_reply(message: Message, state: FSMContext) -> None:
    # Извлекаем order_id из текста команды
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

    # Пересылаем ответ клиенту
    try:
        await message.bot.send_message(
            chat_id=client_user_id,
            text=f"Ответ мастера по заявке #{order_id}:\n\n{message.text}",
        )
        await update_status(order_id, "in_progress")
        await message.answer(f"Ответ отправлен клиенту. Статус заявки #{order_id} → в работе.")
    except Exception:
        # Клиент мог заблокировать бота
        await message.answer(
            "Не удалось отправить сообщение клиенту. "
            "Возможно, клиент заблокировал бота."
        )


@router.message(MasterReply.awaiting_text)
async def handle_master_reply_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте текстовый ответ для клиента.")
