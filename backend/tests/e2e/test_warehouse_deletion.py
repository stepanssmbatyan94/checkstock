"""Удаление ФФ с остатком: остатки и история сохраняются."""

from __future__ import annotations

from tests.e2e.harness import NORTH, SOUTH, Warehouse


class WhenAWarehouseWithStockIsDeleted:
    async def it_reports_what_is_still_held_there(self, warehouse: Warehouse):
        await warehouse.reserve_fbs("SKU-101", SOUTH, 2)

        deleted = await warehouse.delete_warehouse(SOUTH)

        assert deleted.status_code == 200
        body = deleted.json()
        assert body["is_archived"] is True
        assert (body["on_hand"], body["reserved"]) == (10, 2)  # 6 + 4 шт.

    async def it_keeps_the_stock_visible_on_the_stock_screen(
        self, warehouse: Warehouse
    ):
        await warehouse.delete_warehouse(SOUTH)

        assert await warehouse.shown_warehouses() == {NORTH: False, SOUTH: True}
        assert await warehouse.at("SKU-101", SOUTH) == (6, 0, 6)
        assert await warehouse.at("SKU-103", SOUTH) == (4, 0, 4)

    async def it_stops_counting_that_stock_as_available_for_sale(
        self, warehouse: Warehouse
    ):
        await warehouse.delete_warehouse(SOUTH)

        row = await warehouse.row("SKU-101")
        assert (row["total_on_hand"], row["total_available"]) == (16, 10)

    async def it_keeps_the_history(self, warehouse: Warehouse):
        before = await warehouse.history()
        await warehouse.delete_warehouse(SOUTH)

        assert await warehouse.history() == before
        assert SOUTH in {m["to_warehouse"] for m in before}

    async def it_can_be_deleted_twice_with_the_same_result(self, warehouse: Warehouse):
        first = await warehouse.delete_warehouse(SOUTH)
        second = await warehouse.delete_warehouse(SOUTH)

        assert second.status_code == 200
        assert second.json() == first.json()


class WhenWorkingWithADeletedWarehouse:
    async def it_refuses_operations_that_bring_or_promise_goods(
        self, warehouse: Warehouse
    ):
        await warehouse.delete_warehouse(SOUTH)

        for response in (
            await warehouse.receive("SKU-101", SOUTH, 1),
            await warehouse.transfer("SKU-101", NORTH, SOUTH, 1),
            await warehouse.reserve_fbs("SKU-101", SOUTH, 1),
            await warehouse.ship_fbo("SKU-101", SOUTH, 1),
        ):
            assert response.status_code == 409
            assert response.json()["code"] == "warehouse_archived"
        assert await warehouse.at("SKU-101", SOUTH) == (6, 0, 6)

    async def it_lets_the_remaining_stock_be_moved_out(self, warehouse: Warehouse):
        await warehouse.delete_warehouse(SOUTH)

        transfer = await warehouse.transfer("SKU-103", SOUTH, NORTH, 4)
        assert transfer.status_code == 201
        await warehouse.receive_transfer(transfer.json()["id"])

        assert await warehouse.at("SKU-103", NORTH) == (4, 0, 4)
        assert await warehouse.at("SKU-103", SOUTH) == (0, 0, 0)

    async def it_lets_existing_fbs_orders_be_finished(self, warehouse: Warehouse):
        to_ship = (await warehouse.reserve_fbs("SKU-101", SOUTH, 2)).json()
        to_cancel = (await warehouse.reserve_fbs("SKU-101", SOUTH, 1)).json()
        await warehouse.delete_warehouse(SOUTH)

        assert (await warehouse.ship_fbs(to_ship["id"])).status_code == 200
        assert (await warehouse.cancel_fbs(to_cancel["id"])).status_code == 200
        assert await warehouse.at("SKU-101", SOUTH) == (4, 0, 4)

    async def it_still_receives_a_transfer_that_was_already_on_its_way(
        self, warehouse: Warehouse
    ):
        transfer = (await warehouse.transfer("SKU-101", NORTH, SOUTH, 3)).json()
        await warehouse.delete_warehouse(SOUTH)

        assert (await warehouse.receive_transfer(transfer["id"])).status_code == 200
        assert await warehouse.at("SKU-101", SOUTH) == (9, 0, 9)

    async def it_is_not_offered_as_an_alternative_on_shortage(
        self, warehouse: Warehouse
    ):
        await warehouse.delete_warehouse(SOUTH)

        details = (await warehouse.reserve_fbs("SKU-103", NORTH, 2)).json()["details"]
        assert details["alternatives"] == []

    async def it_cannot_be_renamed(self, warehouse: Warehouse):
        await warehouse.delete_warehouse(SOUTH)
        assert (await warehouse.rename_warehouse(SOUTH, "Юг-2")).status_code == 409


class WhenADeletedWarehouseBecomesEmpty:
    async def it_disappears_from_the_stock_screen_but_not_from_history(
        self, empty_warehouse: Warehouse
    ):
        warehouse = empty_warehouse
        await warehouse.receive("SKU-103", SOUTH, 4)
        await warehouse.delete_warehouse(SOUTH)
        transfer = (await warehouse.transfer("SKU-103", SOUTH, NORTH, 4)).json()
        await warehouse.receive_transfer(transfer["id"])

        assert await warehouse.shown_warehouses() == {NORTH: False}
        assert SOUTH in {m["from_warehouse"] for m in await warehouse.history()}


class WhenManagingWarehouses:
    async def it_adds_and_renames(self, warehouse: Warehouse):
        assert (await warehouse.create_warehouse("Запад")).status_code == 201
        assert (await warehouse.rename_warehouse("Запад", "Восток")).status_code == 200

        assert "Восток" in await warehouse.shown_warehouses()
        assert (await warehouse.receive("SKU-101", "Восток", 2)).status_code == 201

    async def it_shows_the_new_name_in_old_history(self, warehouse: Warehouse):
        await warehouse.rename_warehouse(NORTH, "Север-1")
        assert "Север-1" in {m["to_warehouse"] for m in await warehouse.history()}

    async def it_refuses_a_duplicate_name_among_active_warehouses(
        self, warehouse: Warehouse
    ):
        for response in (
            await warehouse.create_warehouse("север"),
            await warehouse.rename_warehouse(SOUTH, NORTH),
        ):
            assert response.status_code == 409
            assert response.json()["code"] == "name_already_taken"

    async def it_allows_reusing_the_name_of_a_deleted_warehouse(
        self, warehouse: Warehouse
    ):
        await warehouse.delete_warehouse(SOUTH)
        assert (await warehouse.create_warehouse(SOUTH)).status_code == 201
