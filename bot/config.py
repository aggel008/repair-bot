"""Конфигурация приложения с валидацией через pydantic-settings.

При запуске недостающие или некорректные переменные окружения роняют процесс
с понятной ошибкой, а не с KeyError посреди работы.
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(min_length=10, description="Токен Telegram-бота от @BotFather")
    master_chat_id: int = Field(description="ID чата мастера (личка или группа)")
    database_path: str = Field(default="orders.db")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()  # type: ignore[call-arg]

# Удобные алиасы для обратной совместимости с уже написанными модулями
BOT_TOKEN: str = settings.bot_token
MASTER_CHAT_ID: int = settings.master_chat_id
DATABASE_PATH: str = settings.database_path

DEVICE_LABELS = {
    "phone": "Телефон",
    "laptop": "Ноутбук",
    "tablet": "Планшет",
    "other": "Другое",
}
