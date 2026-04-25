# Repair Bot — Telegram-бот для приёма заявок на ремонт

## Быстрый старт

### 1. Клонировать и войти в папку
```bash
cd repair-bot
```

### 2. Создать виртуальное окружение
```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Установить зависимости
```bash
pip install -r requirements.txt
```

### 4. Настроить переменные окружения
```bash
cp env.example .env
# Отредактируйте .env: вставьте BOT_TOKEN и MASTER_CHAT_ID
```

**Как получить BOT_TOKEN**: создайте бота через @BotFather в Telegram.  
**Как получить MASTER_CHAT_ID**: отправьте любое сообщение боту @userinfobot.

### 5. Запустить бота
```bash
python -m bot.main
```

---

## Структура проекта

```
repair-bot/
├── bot/
│   ├── main.py              # точка входа, polling
│   ├── config.py            # переменные окружения
│   ├── database/
│   │   ├── db.py            # init_db(), создание таблиц
│   │   └── repository.py    # create_order, get_order, update_status
│   ├── handlers/
│   │   ├── client.py        # FSM: device → problem → phone → confirm
│   │   └── master.py        # /reply_N и пересылка ответа клиенту
│   ├── keyboards/
│   │   └── builder.py       # клавиатуры устройств и подтверждения
│   └── states/
│       └── order.py         # OrderForm, MasterReply (FSM States)
├── .env.example
├── requirements.txt
└── README.md
```

---

## Сценарий использования

**Клиент:**
1. `/start` — выбирает устройство
2. Описывает проблему (текст или голос)
3. Указывает телефон
4. Подтверждает заявку

**Мастер:**
1. Получает уведомление с деталями заявки
2. Отвечает командой `/reply_<номер_заявки>`
3. Вводит текст ответа — бот пересылает клиенту

---

## База данных

Файл `orders.db` создаётся автоматически при первом запуске.

Просмотр заявок:
```bash
sqlite3 orders.db "SELECT id, device_type, phone, status, created_at FROM orders;"
```

---

## Переменные окружения

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен бота от @BotFather |
| `MASTER_CHAT_ID` | ID чата мастера (личка или группа) |
| `DATABASE_PATH` | Путь к SQLite-файлу (по умолчанию `orders.db`) |
