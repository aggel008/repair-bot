from aiogram.fsm.state import State, StatesGroup


class OrderForm(StatesGroup):
    device = State()     # выбор устройства
    problem = State()    # описание проблемы
    phone = State()      # номер телефона
    confirm = State()    # подтверждение


class MasterReply(StatesGroup):
    awaiting_text = State()  # мастер вводит ответ клиенту
