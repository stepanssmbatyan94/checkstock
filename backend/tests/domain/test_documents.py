"""Переходы статусов документов и правила склада."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.documents import FboShipment, FbsOrder, FbsStatus, Transfer
from app.domain.errors import InvalidTransition, ValidationFailed, WarehouseArchived
from app.domain.warehouse import Warehouse

NOW = datetime(2026, 11, 13, tzinfo=UTC)


class WhenConfirmingTwice:
    """Первый вызов возвращает True, повторный — False: менять учёт не нужно."""

    def it_receives_a_transfer_once(self):
        transfer = Transfer.ship(uuid4(), uuid4(), uuid4(), 4, NOW)
        assert transfer.receive(NOW) is True
        assert transfer.receive(NOW) is False

    def it_ships_an_fbs_order_once(self):
        order = FbsOrder.reserve(uuid4(), uuid4(), 3, NOW)
        assert order.ship(NOW) is True
        assert order.ship(NOW) is False

    def it_cancels_an_fbs_order_once(self):
        order = FbsOrder.reserve(uuid4(), uuid4(), 3, NOW)
        assert order.cancel(NOW) is True
        assert order.cancel(NOW) is False

    def it_accepts_an_fbo_shipment_once(self):
        shipment = FboShipment.ship(uuid4(), uuid4(), 5, NOW)
        assert shipment.accept(NOW) is True
        assert shipment.accept(NOW) is False


class WhenAnFbsOrderIsClosed:
    def it_cannot_be_cancelled_after_shipping(self):
        order = FbsOrder.reserve(uuid4(), uuid4(), 3, NOW)
        order.ship(NOW)
        with pytest.raises(InvalidTransition):
            order.cancel(NOW)
        assert order.status is FbsStatus.SHIPPED

    def it_cannot_be_shipped_after_cancelling(self):
        order = FbsOrder.reserve(uuid4(), uuid4(), 3, NOW)
        order.cancel(NOW)
        with pytest.raises(InvalidTransition):
            order.ship(NOW)
        assert order.status is FbsStatus.CANCELLED


class WhenCreatingATransfer:
    def it_rejects_the_same_source_and_destination(self):
        same = uuid4()
        with pytest.raises(ValidationFailed):
            Transfer.ship(uuid4(), same, same, 1, NOW)


class WhenAWarehouseIsDeleted:
    def it_is_archived_only_once(self):
        warehouse = Warehouse.create("Юг")
        assert warehouse.archive(NOW) is True
        assert warehouse.archive(NOW) is False
        assert warehouse.is_archived

    def it_refuses_new_operations_and_renaming(self):
        warehouse = Warehouse.create("Юг")
        warehouse.archive(NOW)
        with pytest.raises(WarehouseArchived):
            warehouse.ensure_active()
        with pytest.raises(WarehouseArchived):
            warehouse.rename("Юг-2")

    @pytest.mark.parametrize("name", ["", "   ", "x" * 101])
    def it_rejects_an_invalid_name(self, name: str):
        with pytest.raises(ValidationFailed):
            Warehouse.create(name)

    def it_trims_the_name(self):
        assert Warehouse.create("  Запад ").name == "Запад"
