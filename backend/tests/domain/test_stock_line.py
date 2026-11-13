"""Правила остатка на одном ФФ. Чистый Python: база не нужна."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.errors import InsufficientStock, ValidationFailed
from app.domain.stock import StockLine


def line(on_hand: int = 0, reserved: int = 0) -> StockLine:
    return StockLine(uuid4(), uuid4(), on_hand=on_hand, reserved=reserved)


class WhenReservingForFbs:
    def it_blocks_goods_without_moving_them(self):
        stock = line(on_hand=10)
        stock.reserve(3)
        assert (stock.on_hand, stock.reserved, stock.available) == (10, 3, 7)

    def it_refuses_more_than_is_available(self):
        stock = line(on_hand=10, reserved=8)
        with pytest.raises(InsufficientStock) as shortage:
            stock.reserve(3)
        assert (shortage.value.requested, shortage.value.available) == (3, 2)
        assert (stock.on_hand, stock.reserved) == (10, 8)


class WhenShipping:
    def it_ships_a_reserved_order_out_of_both_counters(self):
        stock = line(on_hand=10, reserved=3)
        stock.ship_reserved(3)
        assert (stock.on_hand, stock.reserved, stock.available) == (7, 0, 7)

    def it_never_ships_reserved_goods_as_free_stock(self):
        stock = line(on_hand=10, reserved=8)
        with pytest.raises(InsufficientStock):
            stock.ship_available(3)

    def it_returns_goods_to_available_when_a_reservation_is_released(self):
        stock = line(on_hand=10, reserved=3)
        stock.release(3)
        assert (stock.on_hand, stock.reserved, stock.available) == (10, 0, 10)

    def it_refuses_to_release_more_than_is_reserved(self):
        with pytest.raises(ValidationFailed):
            line(on_hand=10, reserved=1).release(2)


class WhenQuantityIsNotPositive:
    @pytest.mark.parametrize("quantity", [0, -1])
    def it_rejects_every_operation(self, quantity: int):
        stock = line(on_hand=10, reserved=5)
        for operation in (
            stock.receive,
            stock.reserve,
            stock.release,
            stock.ship_reserved,
            stock.ship_available,
        ):
            with pytest.raises(ValidationFailed):
                operation(quantity)
        assert (stock.on_hand, stock.reserved) == (10, 5)
