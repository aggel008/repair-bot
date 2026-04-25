import logging
import re

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from bot.config import DEVICE_LABELS
from bot.states.order import OrderForm
from bot.keyboards.builder import device_keyboard, confirm_keyboard, remove_keyboard
from bot.database.repository import create_order
from bot.services.notification import notify_master_new_order

router = Router()

DEVICE_MAP = {
    "Телефон": "phone",
    "Ноутбук": "laptop",
    "Планшет": "tablet",
}

PHONE_RE = re.compile(r"^[\+\d][\d\s\-\(\)]{6,14}\d$")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Привет! Это сервис по ремонту цифровой техники.\n\n"
        "Выберите тип устройства:",
        reply_markup=device_keyboard(),
    )
    await state.set_state(OrderForm.device)


@router.message(OrderForm.device, F.text.in_(DEVICE_MAP))
async def handle_device(message: Message, state: FSMContext) -> None:
    await state.update_data(device=DEVICE_MAP[message.text])
    await message.answer(
        "Опишите проблему. Можно написать текстом или отправить голосовое сообщение.",
        reply_markup=remove_keyboard(),
    )
    await state.set_state(OrderForm.problem)


@router.message(OrderForm.device)
async def handle_device_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, выберите устройство из предложенных вариантов.")


@router.message(OrderForm.problem, F.text)
async def handle_problem_text(message: Message, state: FSMContext) -> None:
    if len(message.text.strip()) < 5:
        await message.answer("Опишите проблему подробнее (минимум 5 символов).")
        return
    await state.update_data(problem=message.text.strip(), voice_id=None)
    await message.answer("Укажите ваш номер телефона для связи:")
    await state.set_state(OrderForm.phone)


@router.message(OrderForm.problem, F.voice)
async def handle_problem_voice(message: Message, state: FSMContext) -> None:
    # Сохраняем file_id голосового — мастер получит пометку о голосовом сообщении
    await state.update_data(
        problem="[голосовое сообщение]",
        voice_id=message.voice.file_id,
    )
    await message.answer("Голосовое принято. Укажите ваш номер телефона для связи:")
    await state.set_state(OrderForm.phone)


@router.message(OrderForm.problem)
async def handle_problem_invalid(message: Message) -> None:
    await message.answer("Отправьте текст или голосовое сообщение с описанием проблемы.")


@router.message(OrderForm.phone, F.text)
async def handle_phone(message: Message, state: FSMContext) -> None:
    phone = message.text.strip()
    if not PHONE_RE.match(phone):
        await message.answer(
            "Введите корректный номер телефона, например: +79001234567"
        )
        return

    data = await state.get_data()
    await state.update_data(phone=phone)

    device_label = DEVICE_LABELS[data["device"]]
    problem_text = data["problem"]
    has_voice = data.get("voice_id") is not None

    summary = (
        f"Ваша заявка:\n\n"
        f"Устройство: {device_label}\n"
        f"Проблема: {problem_text}"
        + (" (+ голосовое сообщение)" if has_voice else "")
        + f"\nТелефон: {phone}"
    )

    await message.answer(
        summary + "\n\nВсё верно?",
        reply_markup=confirm_keyboard(),
    )
    await state.set_state(OrderForm.confirm)


@router.message(OrderForm.phone)
async def handle_phone_invalid(message: Message) -> None:
    await message.answer("Введите номер телефона текстом, например: +79001234567")


@router.message(OrderForm.confirm, F.text == "Подтвердить")
async def handle_confirm(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    order_id = await create_order(
        user_id=message.from_user.id,
        username=message.from_user.username,
        device_type=data["device"],
        problem=data["problem"],
        phone=data["phone"],
        voice_id=data.get("voice_id"),
    )

    await message.answer(
        f"Заявка #{order_id} принята!\n"
        "Мастер свяжется с вами по указанному номеру телефона.",
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
        # Заявка сохранена, но мастер не получил уведомление — не теряем её
        logging.getLogger(__name__).error(
            "Заявка #%s сохранена, но мастер не уведомлён", order_id
        )


@router.message(OrderForm.confirm, F.text == "Отмена")
async def handle_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Заявка отменена. Чтобы начать заново — /start",
        reply_markup=remove_keyboard(),
    )


@router.message(OrderForm.confirm)
async def handle_confirm_invalid(message: Message) -> None:
    await message.answer('Нажмите "Подтвердить" или "Отмена".')


@router.message()
async def fallback(message: Message) -> None:
    """Сообщение вне любого FSM-состояния — подсказываем, что делать."""
    await message.answer(
        "Чтобы создать заявку — /start.\n"
        "Список команд — /help."
    )
