"""Throttling: ограничение частоты сообщений на user_id.

In-memory TTL-кэш: один user_id → timestamp последнего обработанного сообщения.
Если сообщения идут чаще лимита — молча сбрасываем (без флуда юзеру).

Для одного процесса этого достаточно. При горизонтальном масштабировании
заменить на Redis с TTL.
"""
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_limit: float = 0.7) -> None:
        self.rate_limit = rate_limit
        self._last_call: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if event.from_user is None:
            return await handler(event, data)

        user_id = event.from_user.id
        now = time.monotonic()
        last = self._last_call.get(user_id, 0)

        if now - last < self.rate_limit:
            # Сбрасываем флуд без ответа — иначе бот сам станет источником шума
            return None

        self._last_call[user_id] = now
        return await handler(event, data)
