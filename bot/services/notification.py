"""Сервис уведомлений: общается с мастером и клиентом, не зависит от хендлеров.

Поведение зависит от типа чата мастера:

* **Форум-супергруппа** (`is_forum=True`) — на каждую заявку создаётся
  отдельный topic. ВСЕ сообщения по заявке (уведомление, голос, фото,
  переписка, смены статуса) уходят в этот топик через message_thread_id.
  В Telegram это выглядит как отдельное окно на каждую заявку — мастер
  открывает топик и видит всю историю по конкретному клиенту.

* **Обычный чат** — fallback на reply_to_message_id с привязкой к
  корневому уведомлению. Это даёт визуальный «отступ» в чате, но при
  большом количестве заявок всё равно сваливается в одну ленту.
"""
import asyncio
import logging
from typing import Awaitable, Callable, Optional, TypeVar

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter, TelegramNetworkError
from aiogram.types import InputMediaPhoto

from bot.config import MASTER_CHAT_ID, DEVICE_LABELS
from bot.keyboards.inline import order_action_keyboard

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Кэш режима чата мастера: True если форум, False иначе. Заполняется на старте.
_master_is_forum: Optional[bool] = None


async def init_chat_mode(bot: Bot) -> None:
    """Определяет один раз, форум ли чат мастера."""
    global _master_is_forum
    try:
        chat = await bot.get_chat(MASTER_CHAT_ID)
        _master_is_forum = bool(getattr(chat, "is_forum", False))
        logger.info(
            "Чат мастера: %s (is_forum=%s)",
            chat.title or chat.full_name, _master_is_forum,
        )
    except TelegramAPIError as e:
        logger.warning("Не удалось определить режим чата мастера: %s", e)
        _master_is_forum = False


def is_forum_mode() -> bool:
    return bool(_master_is_forum)


async def _with_retry(
    op: Callable[[], Awaitable[T]],
    attempts: int = 3,
    base_delay: float = 1.0,
) -> T:
    last_exc: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            return await op()
        except TelegramRetryAfter as e:
            last_exc = e
            await asyncio.sleep(e.retry_after)
        except TelegramNetworkError as e:
            last_exc = e
            await asyncio.sleep(base_delay * (2 ** attempt))
    assert last_exc is not None
    raise last_exc


async def _create_topic(bot: Bot, order_id: int, device_label: str,
                         model: Optional[str], username: Optional[str]) -> Optional[int]:
    """Создаёт topic в форуме под заявку. Возвращает message_thread_id."""
    name_parts = [f"#{order_id}", device_label]
    if model:
        name_parts.append(model)
    if username:
        name_parts.append(f"@{username}")
    name = " · ".join(name_parts)[:128]  # Telegram-лимит 128 символов
    try:
        topic = await _with_retry(lambda: bot.create_forum_topic(
            chat_id=MASTER_CHAT_ID, name=name,
        ))
        return topic.message_thread_id
    except TelegramAPIError:
        logger.exception("Не удалось создать topic для заявки #%s", order_id)
        return None


async def notify_master_new_order(
    bot: Bot,
    order_id: int,
    device_type: str,
    device_model: Optional[str],
    problem: str,
    voice_id: Optional[str],
    phone: str,
    user_id: int,
    username: Optional[str],
    photo_ids: Optional[list[str]] = None,
) -> tuple[Optional[int], Optional[int]]:
    """Уведомляет мастера. Возвращает (notification_message_id, topic_id).

    Любой из них может быть None при ошибке.
    """
    client_ref = f"@{username}" if username else f"ID {user_id}"
    device_label = DEVICE_LABELS.get(device_type, device_type)
    model_line = f"\nМодель: {device_model}" if device_model else ""

    text = (
        f"📋 Новая заявка №{order_id}\n\n"
        f"Устройство: {device_label}{model_line}\n"
        f"Проблема: {problem}\n"
        f"Телефон: {phone}\n"
        f"Клиент: {client_ref}"
    )

    topic_id: Optional[int] = None
    if is_forum_mode():
        topic_id = await _create_topic(bot, order_id, device_label, device_model, username)

    try:
        # Корневое уведомление с inline-кнопками
        root = await _with_retry(lambda: bot.send_message(
            chat_id=MASTER_CHAT_ID,
            text=text,
            reply_markup=order_action_keyboard(order_id),
            message_thread_id=topic_id,
        ))
        root_id = root.message_id

        if voice_id:
            await _with_retry(lambda: bot.send_voice(
                chat_id=MASTER_CHAT_ID,
                voice=voice_id,
                caption=f"🎤 Голосовое к заявке №{order_id}",
                message_thread_id=topic_id,
                reply_to_message_id=None if topic_id else root_id,
                allow_sending_without_reply=True,
            ))
        if photo_ids:
            for chunk_start in range(0, len(photo_ids), 10):
                chunk = photo_ids[chunk_start:chunk_start + 10]
                media = [InputMediaPhoto(media=fid) for fid in chunk]
                await _with_retry(lambda m=media: bot.send_media_group(
                    chat_id=MASTER_CHAT_ID,
                    media=m,
                    message_thread_id=topic_id,
                    reply_to_message_id=None if topic_id else root_id,
                    allow_sending_without_reply=True,
                ))
        return root_id, topic_id
    except TelegramAPIError:
        logger.exception("Не удалось уведомить мастера о заявке #%s", order_id)
        return None, topic_id


async def forward_client_message_to_master(
    bot: Bot,
    order_id: int,
    text: str,
    username: Optional[str],
    user_id: int,
    notification_message_id: Optional[int] = None,
    topic_id: Optional[int] = None,
) -> None:
    client_ref = f"@{username}" if username else f"ID {user_id}"
    body = f"💬 №{order_id} от {client_ref}:\n\n{text}"
    try:
        await _with_retry(lambda: bot.send_message(
            chat_id=MASTER_CHAT_ID,
            text=body,
            message_thread_id=topic_id,
            reply_to_message_id=None if topic_id else notification_message_id,
            allow_sending_without_reply=True,
        ))
    except TelegramAPIError:
        logger.exception("Не удалось переслать сообщение клиента по заявке #%s", order_id)


async def forward_client_photo_to_master(
    bot: Bot,
    order_id: int,
    photo_file_id: str,
    caption: Optional[str],
    username: Optional[str],
    user_id: int,
    notification_message_id: Optional[int] = None,
    topic_id: Optional[int] = None,
) -> None:
    client_ref = f"@{username}" if username else f"ID {user_id}"
    full_caption = f"📷 №{order_id} от {client_ref}"
    if caption:
        full_caption += f"\n\n{caption}"
    try:
        await _with_retry(lambda: bot.send_photo(
            chat_id=MASTER_CHAT_ID,
            photo=photo_file_id,
            caption=full_caption,
            message_thread_id=topic_id,
            reply_to_message_id=None if topic_id else notification_message_id,
            allow_sending_without_reply=True,
        ))
    except TelegramAPIError:
        logger.exception("Не удалось переслать фото клиента по заявке #%s", order_id)


async def notify_client_status(
    bot: Bot, client_user_id: int, order_id: int, status: str
) -> None:
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
