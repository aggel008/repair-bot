import logging

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext

from bot.config import DEVICE_LABELS
from bot.states.order import OrderForm
from bot.keyboards.builder import (
    device_keyboard,
    phone_keyboard,
    confirm_keyboard,
    remove_keyboard,
)
from bot.database.repository import (
    create_order,
    find_recent_duplicate,
    get_latest_open_order_by_user,
    list_user_orders,
    log_message,
)
from bot.services.notification import (
    notify_master_new_order,
    forward_client_message_to_master,
)
from bot.utils.phone import normalize_phone

logger = logging.getLogger(__name__)

router = Router(name="client")

DEVICE_MAP = {
    "Телефон": "phone",
    "Ноутбук": "laptop",
    "Планшет": "tablet",
}


# --- /start ---

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Здравствуйте! Опишем поломку за минуту.\n\n"
        "Выберите тип устройства:",
        reply_markup=device_keyboard(),
    )
    await state.set_state(OrderForm.device)


# --- Шаг 1: устройство ---

@router.message(OrderForm.device, F.text.in_(DEVICE_MAP))
async def handle_device(message: Message, state: FSMContext) -> None:
    await state.update_data(device=DEVICE_MAP[message.text])
    await message.answer(
        "Опишите проблему — текстом или голосовым сообщением.\n"
        "Например: «не включается после падения, экран чёрный».",
        reply_markup=remove_keyboard(),
    )
    await state.set_state(OrderForm.problem)


@router.message(OrderForm.device)
async def handle_device_invalid(message: Message) -> None:
    await message.answer(
        "Пожалуйста, выберите устройство кнопкой ниже."
    )


# --- Шаг 2: проблема ---

@router.message(OrderForm.problem, F.text)
async def handle_problem_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if len(text) < 5:
        await message.answer(
            "Опишите чуть подробнее — что не работает и когда началось."
        )
        return
    await state.update_data(problem=text, voice_id=None)
    await message.answer(
        "Как с вами связаться? Нажмите кнопку или введите номер вручную.",
        reply_markup=phone_keyboard(),
    )
    await state.set_state(OrderForm.phone)


@router.message(OrderForm.problem, F.voice)
async def handle_problem_voice(message: Message, state: FSMContext) -> None:
    await state.update_data(
        problem="[голосовое сообщение]",
        voice_id=message.voice.file_id,
    )
    await message.answer(
        "Голосовое принято. Как с вами связаться?",
        reply_markup=phone_keyboard(),
    )
    await state.set_state(OrderForm.phone)


@router.message(OrderForm.problem)
async def handle_problem_invalid(message: Message) -> None:
    await message.answer("Отправьте текст или голосовое с описанием проблемы.")


# --- Шаг 3: телефон ---

@router.message(OrderForm.phone, F.contact)
async def handle_phone_contact(message: Message, state: FSMContext) -> None:
    """Принимаем контакт через кнопку — не валидируем regex'ом."""
    phone = normalize_phone(message.contact.phone_number) or message.contact.phone_number
    await _ask_confirmation(message, state, phone)


@router.message(OrderForm.phone, F.text)
async def handle_phone_text(message: Message, state: FSMContext) -> None:
    phone = normalize_phone(message.text)
    if phone is None:
        await message.answer(
            "Не похоже на номер. Пример: +79001234567 "
            "или нажмите кнопку «📱 Отправить мой контакт»."
        )
        return
    await _ask_confirmation(message, state, phone)


@router.message(OrderForm.phone)
async def handle_phone_invalid(message: Message) -> None:
    await message.answer(
        "Отправьте номер текстом или нажмите кнопку «📱 Отправить мой контакт»."
    )


async def _ask_confirmation(message: Message, state: FSMContext, phone: str) -> None:
    data = await state.get_data()
    await state.update_data(phone=phone)

    device_label = DEVICE_LABELS[data["device"]]
    voice_mark = " (+ голосовое)" if data.get("voice_id") else ""

    summary = (
        f"Проверьте заявку:\n\n"
        f"Устройство: {device_label}\n"
        f"Проблема: {data['problem']}{voice_mark}\n"
        f"Телефон: {phone}"
    )
    await message.answer(
        summary + "\n\nВсё верно?",
        reply_markup=confirm_keyboard(),
    )
    await state.set_state(OrderForm.confirm)


# --- Шаг 4: подтверждение ---

@router.message(OrderForm.confirm, F.text == "Подтвердить")
async def handle_confirm(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    # Idempotency: если за последние 60 сек уже есть идентичная заявка — не дублируем
    duplicate_id = await find_recent_duplicate(
        user_id=message.from_user.id,
        device_type=data["device"],
        problem=data["problem"],
        phone=data["phone"],
    )
    if duplicate_id is not None:
        await message.answer(
            f"Заявка №{duplicate_id} уже создана. Мастер свяжется с вами.",
            reply_markup=remove_keyboard(),
        )
        return

    order_id = await create_order(
        user_id=message.from_user.id,
        username=message.from_user.username,
        device_type=data["device"],
        problem=data["problem"],
        phone=data["phone"],
        voice_id=data.get("voice_id"),
    )

    await message.answer(
        f"Заявка №{order_id} принята.\n"
        "Мастер ответит здесь же. Можно дописать в этот чат — всё уйдёт мастеру.",
        reply_markup=remove_keyboard(),
    )

    notified = await notify_master_new_order(
        bot=message.bot,
        order_id=order_id,
        device_type=data["device"],
        problem=data["problem"],
        voice_id=data.get("voice_id"),
        phone=data["phone"],
        user_id=message.from_user.id,
        username=message.from_user.username,
    )
    if not notified:
        logger.error("Заявка #%s сохранена, но мастер не уведомлён", order_id)


@router.message(OrderForm.confirm, F.text == "Изменить")
async def handle_edit(message: Message, state: FSMContext) -> None:
    """Сбрасываем заполненные данные, начинаем заново с шага устройства."""
    await state.clear()
    await message.answer(
        "Хорошо, начнём заново. Выберите устройство:",
        reply_markup=device_keyboard(),
    )
    await state.set_state(OrderForm.device)


@router.message(OrderForm.confirm, F.text == "Отмена")
async def handle_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Заявка отменена. Чтобы начать заново — /start",
        reply_markup=remove_keyboard(),
    )


@router.message(OrderForm.confirm)
async def handle_confirm_invalid(message: Message) -> None:
    await message.answer('Нажмите «Подтвердить», «Изменить» или «Отмена».')


# --- Fallback вне FSM: пересылаем мастеру через bridge ---

@router.message(F.text)
async def fallback_text(message: Message) -> None:
    """Клиент пишет текст вне FSM — ищем его открытую заявку и пересылаем мастеру."""
    order = await get_latest_open_order_by_user(message.from_user.id)
    if order is None:
        await message.answer(
            "Чтобы создать заявку — /start.\nСписок команд — /help."
        )
        return

    await forward_client_message_to_master(
        bot=message.bot,
        order_id=order.id,
        text=message.text,
        username=message.from_user.username,
        user_id=message.from_user.id,
    )
    await log_message(
        order_id=order.id,
        direction="client_to_master",
        text=message.text,
        tg_msg_id=message.message_id,
    )
    await message.answer("Сообщение передано мастеру.")


@router.message(Command("myorders"))
async def cmd_myorders(message: Message) -> None:
    orders = await list_user_orders(message.from_user.id, limit=10)
    if not orders:
        await message.answer("У вас пока нет заявок. Создать — /start")
        return
    lines = ["Ваши заявки:"]
    for o in orders:
        device = DEVICE_LABELS.get(o.device_type, o.device_type)
        lines.append(f"№{o.id} · {device} · {o.status}")
    await message.answer("\n".join(lines))


@router.message()
async def fallback_other(message: Message) -> None:
    await message.answer(
        "Чтобы создать заявку — /start.\nСписок команд — /help."
    )
