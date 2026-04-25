"""Сервис уведомлений: общается с мастером и клиентом, не зависит от хендлеров."""
import logging
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot.config import MASTER_CHAT_ID, DEVICE_LABELS
from bot.keyboards.inline import order_action_keyboard

logger = logging.getLogger(__name__)


async def notify_master_new_order(
    bot: Bot,
    order_id: int,
    device_type: str,
    problem: str,
    voice_id: Optional[str],
    phone: str,
    user_id: int,
    username: Optional[str],
) -> bool:
    """Отправляет мастеру уведомление о новой заявке + сам voice, если есть.

    Возвращает True при успехе. Падать наверх не должно — заявка уже в БД.
    """
    client_ref = f"@{username}" if username else f"ID {user_id}"
    device_label = DEVICE_LABELS.get(device_type, device_type)

    text = (
        f"📋 Новая заявка #{order_id}\n\n"
        f"Устройство: {device_label}\n"
        f"Проблема: {problem}\n"
        f"Телефон: {phone}\n"
        f"Клиент: {client_ref}"
    )

    try:
        await bot.send_message(
            chat_id=MASTER_CHAT_ID,
            text=text,
            reply_markup=order_action_keyboard(order_id),
        )
        if voice_id:
            await bot.send_voice(
                chat_id=MASTER_CHAT_ID,
                voice=voice_id,
                caption=f"🎤 Голосовое к заявке #{order_id}",
            )
        return True
    except TelegramAPIError:
        logger.exception("Не удалось уведомить мастера о заявке #%s", order_id)
        return False


async def forward_client_message_to_master(
    bot: Bot,
    order_id: int,
    text: str,
    username: Optional[str],
    user_id: int,
) -> None:
    """Пересылает реплику клиента (вне FSM) мастеру с привязкой к заявке."""
    client_ref = f"@{username}" if username else f"ID {user_id}"
    body = (
        f"💬 Сообщение по заявке #{order_id} от {client_ref}:\n\n{text}"
    )
    try:
        await bot.send_message(
            chat_id=MASTER_CHAT_ID,
            text=body,
            reply_markup=order_action_keyboard(order_id),
        )
    except TelegramAPIError:
        logger.exception("Не удалось переслать сообщение клиента по заявке #%s", order_id)


async def notify_client_status(
    bot: Bot, client_user_id: int, order_id: int, status: str
) -> None:
    """Уведомляет клиента о смене статуса заявки."""
    msg = {
        "in_progress": f"Ваша заявка №{order_id} принята в работу.",
        "done": f"Заявка №{order_id} закрыта. Спасибо, что обратились!",
    }.get(status)
    if not msg:
        return
    try:
        await bot.send_message(chat_id=client_user_id, text=msg)
    except TelegramAPIError:
        logger.exception("Не удалось уведомить клиента %s о статусе заявки #%s",
                         client_user_id, order_id)
