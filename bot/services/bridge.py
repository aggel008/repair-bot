"""Двусторонний мост клиент↔мастер.

Хранит ID активной заявки, на которую отвечает мастер. Все текстовые
сообщения мастера (вне команд) уходят клиенту этой заявки до момента,
пока мастер не выберет другую заявку или не закроет её.

MVP: in-memory state на одного мастера (single-master deployment).
При необходимости масштабироваться — заменить на Redis с ключом master_id.
"""
from typing import Optional

_active_order_id: Optional[int] = None


def set_active(order_id: int) -> None:
    global _active_order_id
    _active_order_id = order_id


def get_active() -> Optional[int]:
    return _active_order_id


def clear_active() -> None:
    global _active_order_id
    _active_order_id = None
