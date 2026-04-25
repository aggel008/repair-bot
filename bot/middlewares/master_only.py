"""Middleware: пропускает только сообщения из чата мастера.

Закрывает security-дыру: команды вроде /reply_N не должны быть доступны
произвольным пользователям, иначе можно перехватить state и подставить
сообщение от имени мастера.
"""
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.config import MASTER_CHAT_ID


class MasterOnlyMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if event.chat.id != MASTER_CHAT_ID:
            # Молча игнорируем — не выдаём существование master-команд
            return None
        return await handler(event, data)
