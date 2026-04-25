from aiogram.fsm.state import State, StatesGroup


class OrderForm(StatesGroup):
    """FSM шагов оформления заявки клиентом."""
    device = State()     # выбор устройства
    problem = State()    # описание проблемы
    photos = State()     # опциональные фото
    phone = State()      # номер телефона
    confirm = State()    # подтверждение
