from aiogram.fsm.state import State, StatesGroup


class OrderForm(StatesGroup):
    """FSM шагов оформления заявки клиентом."""
    device = State()     # выбор типа устройства
    model = State()      # модель устройства (iPhone 13, MacBook Air M2)
    problem = State()    # описание проблемы
    photos = State()     # опциональные фото
    phone = State()      # номер телефона
    confirm = State()    # подтверждение
