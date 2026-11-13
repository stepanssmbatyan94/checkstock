"""Нехватка на выбранном ФФ при достаточном общем остатке."""

from __future__ import annotations

from tests.e2e.harness import NORTH, SOUTH, Warehouse


class WhenTheChosenWarehouseIsShortButAnotherHasStock:
    """SKU-102: на Юге 0, на Севере 5. Менеджер резервирует 3 на Юге."""

    async def it_refuses_and_says_where_the_goods_are(self, warehouse: Warehouse):
        response = await warehouse.reserve_fbs("SKU-102", SOUTH, 3)

        assert response.status_code == 409
        error = response.json()
        assert error["code"] == "insufficient_stock"
        assert error["details"]["requested"] == 3
        assert error["details"]["available"] == 0
        assert error["details"]["available_elsewhere"] == 5
        assert [
            (a["warehouse_name"], a["available"])
            for a in error["details"]["alternatives"]
        ] == [(NORTH, 5)]

    async def it_changes_nothing(self, warehouse: Warehouse):
        history_before = await warehouse.history()
        await warehouse.reserve_fbs("SKU-102", SOUTH, 3)

        assert await warehouse.at("SKU-102", SOUTH) == (0, 0, 0)
        assert await warehouse.at("SKU-102", NORTH) == (5, 0, 5)
        assert await warehouse.history() == history_before

    async def it_never_takes_goods_from_another_warehouse_silently(
        self, warehouse: Warehouse
    ):
        """На Юге 6, на Севере 10. Запрос 8 на Юге не делится между складами."""
        response = await warehouse.reserve_fbs("SKU-101", SOUTH, 8)

        assert response.status_code == 409
        details = response.json()["details"]
        assert (details["available"], details["available_elsewhere"]) == (6, 10)
        assert await warehouse.at("SKU-101", SOUTH) == (6, 0, 6)
        assert await warehouse.at("SKU-101", NORTH) == (10, 0, 10)

    async def it_applies_to_fbo_and_transfers_too(self, warehouse: Warehouse):
        for response in (
            await warehouse.ship_fbo("SKU-102", SOUTH, 3),
            await warehouse.transfer("SKU-103", NORTH, SOUTH, 2),
        ):
            assert response.status_code == 409
            assert response.json()["code"] == "insufficient_stock"
            assert response.json()["details"]["alternatives"]

    async def it_lets_the_manager_resolve_it_by_moving_goods(
        self, warehouse: Warehouse
    ):
        assert (await warehouse.reserve_fbs("SKU-102", SOUTH, 3)).status_code == 409

        transfer = await warehouse.transfer("SKU-102", NORTH, SOUTH, 3)
        # Пока товар в пути, на Юге его всё ещё нет.
        assert (await warehouse.reserve_fbs("SKU-102", SOUTH, 3)).status_code == 409
        await warehouse.receive_transfer(transfer.json()["id"])

        assert (await warehouse.reserve_fbs("SKU-102", SOUTH, 3)).status_code == 201
        assert await warehouse.at("SKU-102", SOUTH) == (3, 3, 0)
        assert await warehouse.at("SKU-102", NORTH) == (2, 0, 2)


class WhenReservedStockIsNotCountedAsAvailable:
    async def it_reports_only_free_stock_elsewhere(self, warehouse: Warehouse):
        await warehouse.reserve_fbs("SKU-102", NORTH, 4)  # на Севере свободна 1

        details = (await warehouse.reserve_fbs("SKU-102", SOUTH, 3)).json()["details"]
        assert details["available_elsewhere"] == 1


class WhenThereIsNotEnoughAnywhere:
    async def it_refuses_with_no_alternatives(self, warehouse: Warehouse):
        response = await warehouse.reserve_fbs("SKU-103", NORTH, 5)

        assert response.status_code == 409
        details = response.json()["details"]
        assert (details["available"], details["available_elsewhere"]) == (0, 4)

        await warehouse.reserve_fbs("SKU-103", SOUTH, 4)
        details = (await warehouse.reserve_fbs("SKU-103", NORTH, 5)).json()["details"]
        assert details["alternatives"] == []
