"""Перечисления доменной модели — единственный источник правды для статусов и типов."""
from enum import StrEnum


class DeviceType(StrEnum):
    PHONE = "phone"
    LAPTOP = "laptop"
    TABLET = "tablet"
    OTHER = "other"


class OrderStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    AWAITING_CLIENT = "awaiting_client"
    DONE = "done"
    CANCELLED = "cancelled"


CLOSED_STATUSES = frozenset({OrderStatus.DONE, OrderStatus.CANCELLED})
