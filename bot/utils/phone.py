"""Нормализация телефонных номеров в формат E.164.

Принимает любые разумные форматы (+7 900 123-45-67, 89001234567, 7900...)
и приводит к +7XXXXXXXXXX. Возвращает None, если номер не похож на валидный.
"""
import re
from typing import Optional


def normalize_phone(raw: str) -> Optional[str]:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)

    # Российский формат: 8XXXXXXXXXX → +7XXXXXXXXXX
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    # 10 цифр без кода страны — считаем РФ
    if len(digits) == 10:
        digits = "7" + digits

    # Валидный диапазон длины E.164: 8–15 цифр
    if 8 <= len(digits) <= 15:
        return "+" + digits

    return None
