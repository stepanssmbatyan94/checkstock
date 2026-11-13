"""Повторное подтверждение не списывает товар дважды."""

from __future__ import annotations

import asyncio

from tests.e2e.harness import NORTH, SOUTH, Warehouse


def operations(history: list[dict]) -> list[str]:
    return [m["operation"] for m in history]


class WhenAConfirmationIsRepeated:
    async def it_receives_a_transfer_once(self, warehouse: Warehouse):
        transfer = (await warehouse.transfer("SKU-101", NORTH, SOUTH, 4)).json()

        first = await warehouse.receive_transfer(transfer["id"])
        second = await warehouse.receive_transfer(transfer["id"])

        assert (first.status_code, second.status_code) == (200, 200)
        assert second.json() == first.json()
        assert await warehouse.at("SKU-101", SOUTH) == (10, 0, 10)
        assert operations(await warehouse.history()).count("transfer_received") == 1

    async def it_ships_an_fbs_order_once(self, warehouse: Warehouse):
        order = (await warehouse.reserve_fbs("SKU-101", NORTH, 3)).json()

        first = await warehouse.ship_fbs(order["id"])
        second = await warehouse.ship_fbs(order["id"])

        assert second.json() == first.json()
        assert await warehouse.at("SKU-101", NORTH) == (7, 0, 7)
        assert (await warehouse.row("SKU-101"))["in_transit_fbs"] == 3
        assert operations(await warehouse.history()).count("fbs_shipped") == 1

    async def it_cancels_an_fbs_order_once(self, warehouse: Warehouse):
        order = (await warehouse.reserve_fbs("SKU-101", NORTH, 3)).json()

        await warehouse.cancel_fbs(order["id"])
        await warehouse.cancel_fbs(order["id"])

        assert await warehouse.at("SKU-101", NORTH) == (10, 0, 10)
        assert operations(await warehouse.history()).count("fbs_cancelled") == 1

    async def it_accepts_an_fbo_shipment_once(self, warehouse: Warehouse):
        shipment = (await warehouse.ship_fbo("SKU-102", NORTH, 5)).json()

        await warehouse.accept_fbo(shipment["id"])
        await warehouse.accept_fbo(shipment["id"])

        row = await warehouse.row("SKU-102")
        assert (row["in_transit_fbo"], row["at_marketplace"]) == (0, 5)
        assert operations(await warehouse.history()).count("fbo_accepted") == 1


class WhenAnOppositeDecisionArrivesLate:
    async def it_refuses_to_ship_a_cancelled_order(self, warehouse: Warehouse):
        order = (await warehouse.reserve_fbs("SKU-101", NORTH, 3)).json()
        await warehouse.cancel_fbs(order["id"])

        response = await warehouse.ship_fbs(order["id"])

        assert response.status_code == 409
        assert response.json()["code"] == "invalid_transition"
        assert await warehouse.at("SKU-101", NORTH) == (10, 0, 10)

    async def it_refuses_to_cancel_a_shipped_order(self, warehouse: Warehouse):
        order = (await warehouse.reserve_fbs("SKU-101", NORTH, 3)).json()
        await warehouse.ship_fbs(order["id"])

        assert (await warehouse.cancel_fbs(order["id"])).status_code == 409
        assert await warehouse.at("SKU-101", NORTH) == (7, 0, 7)


class WhenACreatingRequestIsSentTwiceWithTheSameKey:
    """Двойной клик или повтор после обрыва сети: ключ Idempotency-Key."""

    async def it_posts_a_receipt_once(self, warehouse: Warehouse):
        first = await warehouse.receive("SKU-102", SOUTH, 7, key="receipt-1")
        second = await warehouse.receive("SKU-102", SOUTH, 7, key="receipt-1")

        assert (first.status_code, second.status_code) == (201, 201)
        assert second.json()["id"] == first.json()["id"]
        assert await warehouse.at("SKU-102", SOUTH) == (7, 0, 7)

    async def it_creates_one_document_for_each_kind_of_shipment(
        self, warehouse: Warehouse
    ):
        for send in (
            lambda: warehouse.reserve_fbs("SKU-101", NORTH, 2, key="fbs-1"),
            lambda: warehouse.ship_fbo("SKU-101", NORTH, 2, key="fbo-1"),
            lambda: warehouse.transfer("SKU-101", NORTH, SOUTH, 2, key="move-1"),
        ):
            assert (await send()).json()["id"] == (await send()).json()["id"]

        # 10 − 2 (FBO) − 2 (перемещение) = 6 физически, 2 в резерве.
        assert await warehouse.at("SKU-101", NORTH) == (6, 2, 4)

    async def it_refuses_the_same_key_with_different_parameters(
        self, warehouse: Warehouse
    ):
        await warehouse.receive("SKU-102", SOUTH, 7, key="receipt-1")

        response = await warehouse.receive("SKU-102", SOUTH, 70, key="receipt-1")

        assert response.status_code == 409
        assert response.json()["code"] == "idempotency_key_reused"
        assert await warehouse.at("SKU-102", SOUTH) == (7, 0, 7)

    async def it_lets_a_failed_request_be_retried_with_the_same_key(
        self, warehouse: Warehouse
    ):
        assert (
            await warehouse.reserve_fbs("SKU-102", SOUTH, 3, key="order-1")
        ).status_code == 409

        await warehouse.receive("SKU-102", SOUTH, 3)

        assert (
            await warehouse.reserve_fbs("SKU-102", SOUTH, 3, key="order-1")
        ).status_code == 201
        assert await warehouse.at("SKU-102", SOUTH) == (3, 3, 0)


class WhenRequestsArriveAtTheSameTime:
    """Настоящая конкуренция: запросы идут параллельно в одну базу."""

    async def it_never_reserves_more_than_is_available(self, warehouse: Warehouse):
        # На Севере 5 шт. SKU-102, одновременно приходят 12 заказов по 1 шт.
        responses = await asyncio.gather(
            *(warehouse.reserve_fbs("SKU-102", NORTH, 1) for _ in range(12))
        )

        codes = sorted(r.status_code for r in responses)
        assert codes == [201] * 5 + [409] * 7
        assert await warehouse.at("SKU-102", NORTH) == (5, 5, 0)

    async def it_applies_a_confirmation_once(self, warehouse: Warehouse):
        transfer = (await warehouse.transfer("SKU-101", NORTH, SOUTH, 4)).json()

        responses = await asyncio.gather(
            *(warehouse.receive_transfer(transfer["id"]) for _ in range(8))
        )

        assert {r.status_code for r in responses} == {200}
        assert await warehouse.at("SKU-101", SOUTH) == (10, 0, 10)
        assert operations(await warehouse.history()).count("transfer_received") == 1

    async def it_applies_one_key_once(self, warehouse: Warehouse):
        responses = await asyncio.gather(
            *(warehouse.receive("SKU-102", SOUTH, 7, key="same") for _ in range(8))
        )

        assert len({r.json()["id"] for r in responses}) == 1
        assert await warehouse.at("SKU-102", SOUTH) == (7, 0, 7)

    async def it_cannot_ship_and_cancel_the_same_order(self, warehouse: Warehouse):
        order = (await warehouse.reserve_fbs("SKU-101", NORTH, 3)).json()

        shipped, cancelled = await asyncio.gather(
            warehouse.ship_fbs(order["id"]), warehouse.cancel_fbs(order["id"])
        )

        assert sorted([shipped.status_code, cancelled.status_code]) == [200, 409]
        on_hand, reserved, _ = await warehouse.at("SKU-101", NORTH)
        assert reserved == 0 and on_hand in (7, 10)
