"""Учёт после прихода, резерва, перемещения, отправки и приёмки."""

from __future__ import annotations

from tests.e2e.harness import NORTH, SOUTH, Warehouse


class WhenTheTestReceiptIsPosted:
    async def it_shows_the_quantities_from_the_task(self, warehouse: Warehouse):
        assert await warehouse.at("SKU-101", NORTH) == (10, 0, 10)
        assert await warehouse.at("SKU-101", SOUTH) == (6, 0, 6)
        assert await warehouse.at("SKU-102", NORTH) == (5, 0, 5)
        assert await warehouse.at("SKU-102", SOUTH) == (0, 0, 0)
        assert await warehouse.at("SKU-103", NORTH) == (0, 0, 0)
        assert await warehouse.at("SKU-103", SOUTH) == (4, 0, 4)

    async def it_records_every_receipt_in_the_history(self, warehouse: Warehouse):
        history = await warehouse.history()
        assert {(m["sku"], m["to_warehouse"], m["quantity"]) for m in history} == {
            ("SKU-101", NORTH, 10),
            ("SKU-101", SOUTH, 6),
            ("SKU-102", NORTH, 5),
            ("SKU-103", SOUTH, 4),
        }
        assert {(m["operation"], m["from_kind"]) for m in history} == {
            ("receipt", "supplier")
        }


class WhenMovingGoodsBetweenWarehouses:
    async def it_keeps_goods_in_transit_until_received(self, warehouse: Warehouse):
        shipped = await warehouse.transfer("SKU-101", NORTH, SOUTH, 4)
        assert shipped.status_code == 201

        # Отправлено: с Севера ушло, на Юг ещё не пришло, 4 шт. в пути.
        assert await warehouse.at("SKU-101", NORTH) == (6, 0, 6)
        assert await warehouse.at("SKU-101", SOUTH) == (6, 0, 6)
        row = await warehouse.row("SKU-101")
        assert row["in_transit_transfer"] == 4
        assert row["total_on_hand"] + row["in_transit_transfer"] == 16

        received = await warehouse.receive_transfer(shipped.json()["id"])
        assert received.json()["status"] == "received"

        assert await warehouse.at("SKU-101", SOUTH) == (10, 0, 10)
        row = await warehouse.row("SKU-101")
        assert (row["in_transit_transfer"], row["total_on_hand"]) == (0, 16)

    async def it_writes_where_from_and_where_to(self, warehouse: Warehouse):
        shipped = await warehouse.transfer("SKU-101", NORTH, SOUTH, 4)
        await warehouse.receive_transfer(shipped.json()["id"])

        received, sent = (await warehouse.history())[:2]
        assert (sent["operation"], sent["quantity"]) == ("transfer_shipped", 4)
        assert (sent["from_warehouse"], sent["to_kind"], sent["to_warehouse"]) == (
            NORTH,
            "transit_transfer",
            SOUTH,
        )
        assert (received["operation"], received["to_kind"]) == (
            "transfer_received",
            "warehouse_available",
        )
        assert received["to_warehouse"] == SOUTH


class WhenSellingByFbs:
    async def it_blocks_goods_on_the_warehouse(self, warehouse: Warehouse):
        assert (await warehouse.reserve_fbs("SKU-101", NORTH, 3)).status_code == 201
        # Физически товар на месте, но доступно меньше.
        assert await warehouse.at("SKU-101", NORTH) == (10, 3, 7)

    async def it_sends_goods_to_the_customer_after_shipping(self, warehouse: Warehouse):
        order = (await warehouse.reserve_fbs("SKU-101", NORTH, 3)).json()
        shipped = await warehouse.ship_fbs(order["id"])
        assert shipped.json()["status"] == "shipped"

        assert await warehouse.at("SKU-101", NORTH) == (7, 0, 7)
        assert (await warehouse.row("SKU-101"))["in_transit_fbs"] == 3

    async def it_returns_goods_to_available_after_cancelling(
        self, warehouse: Warehouse
    ):
        order = (await warehouse.reserve_fbs("SKU-101", NORTH, 3)).json()
        cancelled = await warehouse.cancel_fbs(order["id"])
        assert cancelled.json()["status"] == "cancelled"

        assert await warehouse.at("SKU-101", NORTH) == (10, 0, 10)
        assert (await warehouse.row("SKU-101"))["in_transit_fbs"] == 0

    async def it_does_not_let_reserved_goods_leave_another_way(
        self, warehouse: Warehouse
    ):
        await warehouse.reserve_fbs("SKU-101", NORTH, 8)  # доступно осталось 2

        assert (await warehouse.transfer("SKU-101", NORTH, SOUTH, 3)).status_code == 409
        assert (await warehouse.ship_fbo("SKU-101", NORTH, 3)).status_code == 409
        assert (await warehouse.reserve_fbs("SKU-101", NORTH, 3)).status_code == 409
        assert await warehouse.at("SKU-101", NORTH) == (10, 8, 2)


class WhenShippingByFbo:
    async def it_leaves_the_warehouse_and_stays_in_transit_until_accepted(
        self, warehouse: Warehouse
    ):
        shipment = await warehouse.ship_fbo("SKU-102", NORTH, 5)
        assert shipment.status_code == 201

        assert await warehouse.at("SKU-102", NORTH) == (0, 0, 0)
        row = await warehouse.row("SKU-102")
        assert (row["in_transit_fbo"], row["at_marketplace"]) == (5, 0)

        accepted = await warehouse.accept_fbo(shipment.json()["id"])
        assert accepted.json()["status"] == "accepted"

        row = await warehouse.row("SKU-102")
        assert (row["in_transit_fbo"], row["at_marketplace"]) == (0, 5)


class WhenARequestIsInvalid:
    async def it_rejects_a_non_positive_quantity(self, warehouse: Warehouse):
        for response in (
            await warehouse.receive("SKU-101", NORTH, 0),
            await warehouse.reserve_fbs("SKU-101", NORTH, -1),
            await warehouse.transfer("SKU-101", NORTH, SOUTH, 0),
            await warehouse.ship_fbo("SKU-101", NORTH, -5),
        ):
            assert response.status_code == 422
            assert response.json()["code"] == "validation_failed"
        assert await warehouse.at("SKU-101", NORTH) == (10, 0, 10)

    async def it_rejects_a_transfer_to_the_same_warehouse(self, warehouse: Warehouse):
        assert (await warehouse.transfer("SKU-101", NORTH, NORTH, 1)).status_code == 422
