"""Остаток одного товара на одном ФФ и правила его изменения."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.errors import InsufficientStock, ValidationFailed


def ensure_positive(quantity: int) -> None:
    if quantity <= 0:
        raise ValidationFailed("Количество должно быть больше нуля")


@dataclass
class StockLine:
    """Инвариант: 0 <= reserved <= on_hand.

    on_hand   — физически лежит на складе;
    reserved  — из них заблокировано под заказы FBS;
    available — можно резервировать, перемещать и отправлять.

    Тот же инвариант продублирован CHECK-ограничениями в PostgreSQL:
    если код ошибётся, база не даст записать отрицательный остаток.
    """

    product_id: UUID
    warehouse_id: UUID
    on_hand: int = 0
    reserved: int = 0

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved

    def receive(self, quantity: int) -> None:
        """Товар пришёл на склад: приход от поставщика или приёмка перемещения."""
        ensure_positive(quantity)
        self.on_hand += quantity

    def reserve(self, quantity: int) -> None:
        """Заблокировать под заказ FBS. Физически товар остаётся на складе."""
        self._ensure_available(quantity)
        self.reserved += quantity

    def release(self, quantity: int) -> None:
        """Снять резерв (отмена заказа FBS)."""
        self._ensure_reserved(quantity)
        self.reserved -= quantity

    def ship_reserved(self, quantity: int) -> None:
        """Отправить зарезервированное: товар покидает склад, резерв закрывается."""
        self._ensure_reserved(quantity)
        self.reserved -= quantity
        self.on_hand -= quantity

    def ship_available(self, quantity: int) -> None:
        """Отправить свободный товар (перемещение или FBO). Резерв трогать нельзя."""
        self._ensure_available(quantity)
        self.on_hand -= quantity

    def _ensure_available(self, quantity: int) -> None:
        ensure_positive(quantity)
        if quantity > self.available:
            raise InsufficientStock(
                product_id=self.product_id,
                warehouse_id=self.warehouse_id,
                requested=quantity,
                available=self.available,
            )

    def _ensure_reserved(self, quantity: int) -> None:
        ensure_positive(quantity)
        if quantity > self.reserved:
            raise ValidationFailed(
                f"В резерве {self.reserved}, нельзя снять или отправить {quantity}"
            )
