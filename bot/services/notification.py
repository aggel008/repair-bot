"""Сервис уведомлений: общается с мастером и клиентом, не зависит от хендлеров."""
import logging
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot.config import MASTER_CHAT_ID, DEVICE_LABELS

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
        f"Клиент: {client_ref}\n\n"
        f"Ответить клиенту: /reply_{order_id}"
    )

    try:
        await bot.send_message(chat_id=MASTER_CHAT_ID, text=text)
        # Если есть голосовое — пересылаем мастеру отдельным сообщением
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
