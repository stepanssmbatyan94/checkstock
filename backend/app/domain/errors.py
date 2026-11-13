"""Ошибки предметной области. HTTP-слой переводит их в коды ответа."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


class DomainError(Exception):
    code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationFailed(DomainError):
    code = "validation_failed"


class NotFound(DomainError):
    code = "not_found"


class NameAlreadyTaken(DomainError):
    code = "name_already_taken"


class WarehouseArchived(DomainError):
    """Операция требует действующий ФФ, а он удалён (в архиве)."""

    code = "warehouse_archived"


class InvalidTransition(DomainError):
    """Документ уже в состоянии, из которого запрошенный переход невозможен."""

    code = "invalid_transition"


class IdempotencyKeyReused(DomainError):
    """Тот же ключ идемпотентности пришёл с другими параметрами операции."""

    code = "idempotency_key_reused"


@dataclass(frozen=True)
class StockAlternative:
    warehouse_id: UUID
    warehouse_name: str
    available: int


@dataclass(eq=False)
class InsufficientStock(DomainError):
    """На выбранном ФФ не хватает доступного товара.

    `alternatives` заполняет слой приложения: где этот товар доступен ещё.
    Так менеджер видит не просто отказ, а что делать дальше.
    """

    product_id: UUID
    warehouse_id: UUID
    requested: int
    available: int
    alternatives: list[StockAlternative] = field(default_factory=list)

    code = "insufficient_stock"

    def __post_init__(self) -> None:
        DomainError.__init__(
            self,
            f"Недостаточно товара на выбранном ФФ: запрошено {self.requested}, "
            f"доступно {self.available}",
        )

    @property
    def available_elsewhere(self) -> int:
        return sum(a.available for a in self.alternatives)
