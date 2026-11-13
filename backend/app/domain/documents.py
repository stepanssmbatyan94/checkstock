"""Документы движения: перемещение между ФФ, заказ FBS, поставка FBO.

Каждый документ — маленький конечный автомат. Методы перехода возвращают
True, если переход случился сейчас, и False, если документ уже был в этом
состоянии. На этом держится защита от повторного подтверждения: обработчик
меняет остатки только когда получил True.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from app.domain.errors import InvalidTransition, ValidationFailed
from app.domain.stock import ensure_positive


class TransferStatus(StrEnum):
    SHIPPED = "shipped"  # в пути между ФФ
    RECEIVED = "received"


class FbsStatus(StrEnum):
    RESERVED = "reserved"  # товар заблокирован на ФФ
    SHIPPED = "shipped"  # едет к клиенту
    CANCELLED = "cancelled"


class FboStatus(StrEnum):
    IN_TRANSIT = "in_transit"  # едет на склад маркетплейса
    ACCEPTED = "accepted"


@dataclass
class Transfer:
    id: UUID
    product_id: UUID
    from_warehouse_id: UUID
    to_warehouse_id: UUID
    quantity: int
    status: TransferStatus
    shipped_at: datetime
    received_at: datetime | None = None

    def __post_init__(self) -> None:
        self.status = TransferStatus(self.status)

    @classmethod
    def ship(
        cls,
        product_id: UUID,
        from_warehouse_id: UUID,
        to_warehouse_id: UUID,
        quantity: int,
        now: datetime,
    ) -> Transfer:
        ensure_positive(quantity)
        if from_warehouse_id == to_warehouse_id:
            raise ValidationFailed("Нельзя переместить товар на тот же ФФ")
        return cls(
            id=uuid4(),
            product_id=product_id,
            from_warehouse_id=from_warehouse_id,
            to_warehouse_id=to_warehouse_id,
            quantity=quantity,
            status=TransferStatus.SHIPPED,
            shipped_at=now,
        )

    def receive(self, now: datetime) -> bool:
        if self.status is TransferStatus.RECEIVED:
            return False
        self.status = TransferStatus.RECEIVED
        self.received_at = now
        return True


@dataclass
class FbsOrder:
    id: UUID
    product_id: UUID
    warehouse_id: UUID
    quantity: int
    status: FbsStatus
    reserved_at: datetime
    closed_at: datetime | None = None

    def __post_init__(self) -> None:
        self.status = FbsStatus(self.status)

    @classmethod
    def reserve(
        cls, product_id: UUID, warehouse_id: UUID, quantity: int, now: datetime
    ) -> FbsOrder:
        ensure_positive(quantity)
        return cls(
            id=uuid4(),
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            status=FbsStatus.RESERVED,
            reserved_at=now,
        )

    def ship(self, now: datetime) -> bool:
        if self.status is FbsStatus.SHIPPED:
            return False
        if self.status is FbsStatus.CANCELLED:
            raise InvalidTransition("Заказ FBS отменён, отправить его нельзя")
        self.status = FbsStatus.SHIPPED
        self.closed_at = now
        return True

    def cancel(self, now: datetime) -> bool:
        if self.status is FbsStatus.CANCELLED:
            return False
        if self.status is FbsStatus.SHIPPED:
            raise InvalidTransition("Заказ FBS уже отправлен, отменить его нельзя")
        self.status = FbsStatus.CANCELLED
        self.closed_at = now
        return True


@dataclass
class FboShipment:
    id: UUID
    product_id: UUID
    warehouse_id: UUID
    quantity: int
    status: FboStatus
    shipped_at: datetime
    accepted_at: datetime | None = None

    def __post_init__(self) -> None:
        self.status = FboStatus(self.status)

    @classmethod
    def ship(
        cls, product_id: UUID, warehouse_id: UUID, quantity: int, now: datetime
    ) -> FboShipment:
        ensure_positive(quantity)
        return cls(
            id=uuid4(),
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            status=FboStatus.IN_TRANSIT,
            shipped_at=now,
        )

    def accept(self, now: datetime) -> bool:
        if self.status is FboStatus.ACCEPTED:
            return False
        self.status = FboStatus.ACCEPTED
        self.accepted_at = now
        return True
