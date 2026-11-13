"""Склад фулфилмента (ФФ)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.errors import ValidationFailed, WarehouseArchived

MAX_NAME_LENGTH = 100


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValidationFailed("Название ФФ не может быть пустым")
    if len(cleaned) > MAX_NAME_LENGTH:
        raise ValidationFailed(f"Название ФФ длиннее {MAX_NAME_LENGTH} символов")
    return cleaned


@dataclass
class Warehouse:
    """Удаление ФФ — это архивирование, а не DELETE.

    Строка склада остаётся в базе, поэтому остатки и история продолжают
    на неё ссылаться: товар по-прежнему числится на удалённом ФФ, пока его
    не вывезут. Архивный ФФ закрыт для новых операций, которые привозят
    товар или обещают его покупателю.
    """

    id: UUID
    name: str
    deleted_at: datetime | None = None

    @classmethod
    def create(cls, name: str) -> Warehouse:
        return cls(id=uuid4(), name=_clean_name(name))

    @property
    def is_archived(self) -> bool:
        return self.deleted_at is not None

    def rename(self, name: str) -> None:
        self.ensure_active()
        self.name = _clean_name(name)

    def archive(self, now: datetime) -> bool:
        """Возвращает False, если ФФ уже в архиве: повторное удаление безвредно."""
        if self.is_archived:
            return False
        self.deleted_at = now
        return True

    def ensure_active(self) -> None:
        if self.is_archived:
            raise WarehouseArchived(
                f"ФФ «{self.name}» удалён: новые операции с ним недоступны"
            )
