"""Хендлеры мастера: callback-кнопки и пересылка ответов клиенту через bridge.

Все хендлеры этого роутера защищены MasterOnlyMiddleware — сообщения от
посторонних пользователей сюда не попадают.
"""
import logging

from aiogram import Router, F
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from bot.config import MASTER_CHAT_ID
from bot.database.repository import (
    get_order,
    get_order_by_notification_msg,
    get_order_by_topic_id,
    list_open_orders,
    log_message,
    update_status,
)
from bot.domain.enums import OrderStatus
from bot.keyboards.inline import OrderAction, order_action_keyboard
from bot.services import bridge
from bot.services.notification import notify_client_status

logger = logging.getLogger(__name__)

router = Router(name="master")
# Закрытие security-дыры: все хендлеры этого роутера сработают только в чате мастера.
router.message.filter(F.chat.id == MASTER_CHAT_ID)
router.callback_query.filter(F.message.chat.id == MASTER_CHAT_ID)


class BridgeActive(BaseFilter):
    """Матчится только если у мастера есть активный диалог. Иначе — пропуск
    события дальше по цепочке роутеров (например, в client для /start)."""
    async def __call__(self, message: Message) -> bool:
        return bridge.get_active() is not None


# --- Callback-кнопки на уведомлении ---

@router.callback_query(OrderAction.filter(F.action == "reply"))
async def cb_reply(query: CallbackQuery, callback_data: OrderAction) -> None:
    order = await get_order(callback_data.order_id)
    if order is None:
        await query.answer("Заявка не найдена", show_alert=True)
        return
    if order.status in ("done", "cancelled"):
        await query.answer(f"Заявка уже {order.status}", show_alert=True)
        return

    bridge.set_active(order.id)
    await query.answer()
    await query.message.answer(
        f"Активная заявка: №{order.id} (тел. {order.phone}).\n"
        f"Все ваши следующие сообщения уйдут клиенту.\n"
        f"Чтобы выйти из диалога — /done"
    )


@router.callback_query(OrderAction.filter(F.action == "progress"))
async def cb_progress(query: CallbackQuery, callback_data: OrderAction) -> None:
    order = await get_order(callback_data.order_id)
    if order is None:
        await query.answer("Заявка не найдена", show_alert=True)
        return

    await update_status(
        order.id, OrderStatus.IN_PROGRESS.value,
        actor="master", actor_id=query.from_user.id,
    )
    await notify_client_status(query.bot, order.user_id, order.id, OrderStatus.IN_PROGRESS.value)
    await query.answer("Статус → в работе")
    try:
        await query.message.edit_reply_markup(
            reply_markup=order_action_keyboard(order.id, status=OrderStatus.IN_PROGRESS.value)
        )
    except Exception:
        pass


@router.callback_query(OrderAction.filter(F.action == "close"))
async def cb_close(query: CallbackQuery, callback_data: OrderAction) -> None:
    order = await get_order(callback_data.order_id)
    if order is None:
        await query.answer("Заявка не найдена", show_alert=True)
        return

    await update_status(
        order.id, OrderStatus.DONE.value,
        actor="master", actor_id=query.from_user.id,
    )
    await notify_client_status(query.bot, order.user_id, order.id, OrderStatus.DONE.value)
    if bridge.get_active() == order.id:
        bridge.clear_active()
    await query.answer("Заявка закрыта")
    try:
        await query.message.edit_reply_markup(
            reply_markup=order_action_keyboard(order.id, status=OrderStatus.DONE.value)
        )
    except Exception:
        pass


@router.message(F.text == "/orders")
async def cmd_orders(message: Message) -> None:
    """Список открытых заявок для мастера."""
    orders = await list_open_orders(limit=20)
    if not orders:
        await message.answer("Открытых заявок нет.")
        return
    lines = ["Открытые заявки:"]
    for o in orders:
        client = f"@{o.username}" if o.username else f"id{o.user_id}"
        lines.append(
            f"№{o.id} · {o.device_type} · {o.status} · {o.phone} · {client}"
        )
    lines.append("\nЧтобы ответить — откройте уведомление с кнопками.")
    await message.answer("\n".join(lines))


# --- Команды и текст мастера ---

@router.message(F.text == "/done")
async def cmd_done(message: Message) -> None:
    if bridge.get_active() is None:
        await message.answer("Активного диалога нет.")
        return
    bridge.clear_active()
    await message.answer("Вы вышли из диалога.")


async def _deliver_to_client(message: Message, order) -> None:
    """Общая логика доставки текста мастера → клиенту с логированием."""
    try:
        await message.bot.send_message(
            chat_id=order.user_id,
            text=f"💬 Ответ мастера по заявке №{order.id}:\n\n{message.text}",
        )
        await log_message(
            order_id=order.id,
            direction="master_to_client",
            text=message.text,
            tg_msg_id=message.message_id,
        )
        if order.status == OrderStatus.NEW.value:
            await update_status(
                order.id, OrderStatus.IN_PROGRESS.value,
                actor="master", actor_id=message.from_user.id,
            )
        await message.reply(f"✓ доставлено клиенту (заявка №{order.id})")
    except Exception:
        logger.exception("Ответ клиенту по заявке #%s не доставлен", order.id)
        await message.reply(
            "Не удалось доставить сообщение клиенту "
            "(возможно, бот заблокирован)."
        )


class IsReplyToOrderNotification(BaseFilter):
    """Матчится только если сообщение — reply на корневое уведомление заявки."""
    async def __call__(self, message: Message) -> bool:
        if message.reply_to_message is None:
            return False
        order = await get_order_by_notification_msg(message.reply_to_message.message_id)
        return order is not None


class IsInOrderTopic(BaseFilter):
    """Матчится, если сообщение в топике форума, привязанном к заявке."""
    async def __call__(self, message: Message) -> bool:
        if message.message_thread_id is None:
            return False
        order = await get_order_by_topic_id(message.message_thread_id)
        return order is not None


@router.message(F.text & ~F.text.startswith("/"), IsInOrderTopic())
async def handle_master_in_topic(message: Message) -> None:
    """В форум-режиме: мастер пишет в топике заявки → клиенту этой заявки.

    Никаких кнопок «Ответить» не нужно — топик сам определяет контекст.
    """
    order = await get_order_by_topic_id(message.message_thread_id)
    if order is None:
        return
    bridge.set_active(order.id)
    await _deliver_to_client(message, order)


@router.message(F.text & ~F.text.startswith("/"), IsReplyToOrderNotification())
async def handle_master_swipe_reply(message: Message) -> None:
    """Не-форум: мастер свайп-реплаит на уведомление → клиенту этой заявки."""
    order = await get_order_by_notification_msg(message.reply_to_message.message_id)
    if order is None:
        return
    bridge.set_active(order.id)
    await _deliver_to_client(message, order)


@router.message(F.text & ~F.text.startswith("/"), BridgeActive())
async def handle_master_text(message: Message) -> None:
    """Текст от мастера (без свайп-реплая, при активном bridge) → клиенту."""
    active_id = bridge.get_active()
    order = await get_order(active_id) if active_id else None
    if order is None:
        bridge.clear_active()
        await message.reply("Заявка пропала из БД. Диалог закрыт.")
        return
    await _deliver_to_client(message, order)
