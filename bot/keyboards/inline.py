"""Inline-клавиатуры и callback_data factories."""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class OrderAction(CallbackData, prefix="order"):
    """Действие мастера над заявкой. action: reply | progress | close."""
    order_id: int
    action: str


def order_action_keyboard(order_id: int, status: str = "new") -> InlineKeyboardMarkup:
    """Кнопки управления заявкой для мастера. Адаптируется под статус."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="💬 Ответить",
        callback_data=OrderAction(order_id=order_id, action="reply").pack(),
    )
    if status == "new":
        builder.button(
            text="✅ В работе",
            callback_data=OrderAction(order_id=order_id, action="progress").pack(),
        )
    if status != "done":
        builder.button(
            text="🏁 Закрыть",
            callback_data=OrderAction(order_id=order_id, action="close").pack(),
        )
    builder.adjust(1, 2)
    return builder.as_markup()
