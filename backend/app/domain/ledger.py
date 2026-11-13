"""Журнал движений — источник правды об учёте.

Каждая операция записывается как перенос количества с одного счёта на
другой (двойная запись). Товар не появляется и не исчезает: сколько ушло
с одного счёта, столько пришло на другой. Поэтому любой остаток можно
пересчитать из журнала и сверить с таблицей остатков.

Резерв FBS — тоже перенос: со счёта «доступно на ФФ» на счёт «в резерве
на ФФ». Физически товар лежит на том же складе, но в учёте это разные
счета, и история показывает резерв как отдельную операцию.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid4


class AccountKind(StrEnum):
    SUPPLIER = "supplier"  # внешний источник прихода
    WAREHOUSE_AVAILABLE = "warehouse_available"  # на ФФ, доступно
    WAREHOUSE_RESERVED = "warehouse_reserved"  # на ФФ, в резерве FBS
    TRANSIT_TRANSFER = "transit_transfer"  # в пути между ФФ
    TRANSIT_FBO = "transit_fbo"  # в пути на склад маркетплейса
    MARKETPLACE = "marketplace"  # принято складом маркетплейса
    TRANSIT_FBS = "transit_fbs"  # в пути к клиенту


class Operation(StrEnum):
    RECEIPT = "receipt"
    TRANSFER_SHIPPED = "transfer_shipped"
    TRANSFER_RECEIVED = "transfer_received"
    FBS_RESERVED = "fbs_reserved"
    FBS_CANCELLED = "fbs_cancelled"
    FBS_SHIPPED = "fbs_shipped"
    FBO_SHIPPED = "fbo_shipped"
    FBO_ACCEPTED = "fbo_accepted"


@dataclass(frozen=True)
class Account:
    """Счёт учёта. Для складских счетов и «в пути между ФФ» указан склад
    (у транзита — склад назначения), у остальных склада нет."""

    kind: AccountKind
    warehouse_id: UUID | None = None


def _available(warehouse_id: UUID) -> Account:
    return Account(AccountKind.WAREHOUSE_AVAILABLE, warehouse_id)


def _reserved(warehouse_id: UUID) -> Account:
    return Account(AccountKind.WAREHOUSE_RESERVED, warehouse_id)


@dataclass(frozen=True)
class Movement:
    id: UUID
    operation: Operation
    product_id: UUID
    quantity: int
    source: Account
    destination: Account
    document_id: UUID | None = None

    @classmethod
    def receipt(cls, product_id: UUID, warehouse_id: UUID, quantity: int) -> Movement:
        return cls(
            uuid4(),
            Operation.RECEIPT,
            product_id,
            quantity,
            Account(AccountKind.SUPPLIER),
            _available(warehouse_id),
        )

    @classmethod
    def transfer_shipped(
        cls,
        document_id: UUID,
        product_id: UUID,
        from_warehouse_id: UUID,
        to_warehouse_id: UUID,
        quantity: int,
    ) -> Movement:
        return cls(
            uuid4(),
            Operation.TRANSFER_SHIPPED,
            product_id,
            quantity,
            _available(from_warehouse_id),
            Account(AccountKind.TRANSIT_TRANSFER, to_warehouse_id),
            document_id,
        )

    @classmethod
    def transfer_received(
        cls, document_id: UUID, product_id: UUID, to_warehouse_id: UUID, quantity: int
    ) -> Movement:
        return cls(
            uuid4(),
            Operation.TRANSFER_RECEIVED,
            product_id,
            quantity,
            Account(AccountKind.TRANSIT_TRANSFER, to_warehouse_id),
            _available(to_warehouse_id),
            document_id,
        )

    @classmethod
    def fbs_reserved(
        cls, document_id: UUID, product_id: UUID, warehouse_id: UUID, quantity: int
    ) -> Movement:
        return cls(
            uuid4(),
            Operation.FBS_RESERVED,
            product_id,
            quantity,
            _available(warehouse_id),
            _reserved(warehouse_id),
            document_id,
        )

    @classmethod
    def fbs_cancelled(
        cls, document_id: UUID, product_id: UUID, warehouse_id: UUID, quantity: int
    ) -> Movement:
        return cls(
            uuid4(),
            Operation.FBS_CANCELLED,
            product_id,
            quantity,
            _reserved(warehouse_id),
            _available(warehouse_id),
            document_id,
        )

    @classmethod
    def fbs_shipped(
        cls, document_id: UUID, product_id: UUID, warehouse_id: UUID, quantity: int
    ) -> Movement:
        return cls(
            uuid4(),
            Operation.FBS_SHIPPED,
            product_id,
            quantity,
            _reserved(warehouse_id),
            Account(AccountKind.TRANSIT_FBS),
            document_id,
        )

    @classmethod
    def fbo_shipped(
        cls, document_id: UUID, product_id: UUID, warehouse_id: UUID, quantity: int
    ) -> Movement:
        return cls(
            uuid4(),
            Operation.FBO_SHIPPED,
            product_id,
            quantity,
            _available(warehouse_id),
            Account(AccountKind.TRANSIT_FBO),
            document_id,
        )

    @classmethod
    def fbo_accepted(
        cls, document_id: UUID, product_id: UUID, quantity: int
    ) -> Movement:
        return cls(
            uuid4(),
            Operation.FBO_ACCEPTED,
            product_id,
            quantity,
            Account(AccountKind.TRANSIT_FBO),
            Account(AccountKind.MARKETPLACE),
            document_id,
        )
