"""Мини-язык для сценариев: тесты читаются как действия менеджера.

Каждое изменяющее действие сразу после себя запускает сверку журнала с
остатками. Требование «остатки сходятся после каждого действия» проверяется
буквально — после каждого запроса, а не один раз в конце теста.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from httpx import AsyncClient, Response

from app import seed

NORTH = "Север"
SOUTH = "Юг"


class Warehouse:
    def __init__(self, client: AsyncClient) -> None:
        self._client = client
        self._warehouses: dict[str, UUID] = {
            NORTH: seed.NORTH_ID,
            SOUTH: seed.SOUTH_ID,
        }

    # ── Действия ─────────────────────────────────────────────────────────

    async def post_test_receipt(self) -> None:
        for sku, (_, _, north, south) in seed.PRODUCTS.items():
            for name, quantity in ((NORTH, north), (SOUTH, south)):
                if quantity:
                    assert (await self.receive(sku, name, quantity)).status_code == 201

    async def receive(
        self, sku: str, warehouse: str, quantity: int, key: str | None = None
    ) -> Response:
        return await self._post(
            "/api/receipts", self._body(sku, warehouse, quantity), key
        )

    async def transfer(
        self, sku: str, source: str, target: str, quantity: int, key: str | None = None
    ) -> Response:
        body = {
            "product_id": str(_product_id(sku)),
            "from_warehouse_id": str(self._warehouses[source]),
            "to_warehouse_id": str(self._warehouses[target]),
            "quantity": quantity,
        }
        return await self._post("/api/transfers", body, key)

    async def receive_transfer(self, transfer_id: str) -> Response:
        return await self._post(f"/api/transfers/{transfer_id}/receive")

    async def reserve_fbs(
        self, sku: str, warehouse: str, quantity: int, key: str | None = None
    ) -> Response:
        return await self._post(
            "/api/fbs-orders", self._body(sku, warehouse, quantity), key
        )

    async def ship_fbs(self, order_id: str) -> Response:
        return await self._post(f"/api/fbs-orders/{order_id}/ship")

    async def cancel_fbs(self, order_id: str) -> Response:
        return await self._post(f"/api/fbs-orders/{order_id}/cancel")

    async def ship_fbo(
        self, sku: str, warehouse: str, quantity: int, key: str | None = None
    ) -> Response:
        return await self._post(
            "/api/fbo-shipments", self._body(sku, warehouse, quantity), key
        )

    async def accept_fbo(self, shipment_id: str) -> Response:
        return await self._post(f"/api/fbo-shipments/{shipment_id}/accept")

    async def create_warehouse(self, name: str) -> Response:
        response = await self._post("/api/warehouses", {"name": name})
        if response.status_code == 201:
            self._warehouses[name] = UUID(response.json()["id"])
        return response

    async def rename_warehouse(self, name: str, new_name: str) -> Response:
        response = await self._client.patch(
            f"/api/warehouses/{self._warehouses[name]}", json={"name": new_name}
        )
        if response.status_code == 200:
            self._warehouses[new_name] = self._warehouses[name]
        await self.assert_reconciled()
        return response

    async def delete_warehouse(self, name: str) -> Response:
        response = await self._client.delete(
            f"/api/warehouses/{self._warehouses[name]}"
        )
        await self.assert_reconciled()
        return response

    # ── Наблюдения ───────────────────────────────────────────────────────

    async def row(self, sku: str) -> dict[str, Any]:
        overview = (await self._client.get("/api/stock")).json()
        return next(row for row in overview["rows"] if row["sku"] == sku)

    async def at(self, sku: str, warehouse: str) -> tuple[int, int, int]:
        """(физически, в резерве, доступно) для товара на ФФ."""
        warehouse_id = str(self._warehouses[warehouse])
        for cell in (await self.row(sku))["cells"]:
            if cell["warehouse_id"] == warehouse_id:
                return cell["on_hand"], cell["reserved"], cell["available"]
        raise AssertionError(f"ФФ «{warehouse}» не показан на экране остатков")

    async def shown_warehouses(self) -> dict[str, bool]:
        """Название ФФ на экране остатков → в архиве ли он."""
        overview = (await self._client.get("/api/stock")).json()
        return {w["name"]: w["is_archived"] for w in overview["warehouses"]}

    async def history(self) -> list[dict[str, Any]]:
        return (await self._client.get("/api/movements")).json()

    async def assert_reconciled(self) -> None:
        result = (await self._client.get("/api/reconciliation")).json()
        assert result["consistent"], f"Учёт разошёлся: {result['discrepancies']}"

    # ── Внутреннее ───────────────────────────────────────────────────────

    def _body(self, sku: str, warehouse: str, quantity: int) -> dict[str, Any]:
        return {
            "product_id": str(_product_id(sku)),
            "warehouse_id": str(self._warehouses[warehouse]),
            "quantity": quantity,
        }

    async def _post(
        self, path: str, body: dict[str, Any] | None = None, key: str | None = None
    ) -> Response:
        headers = {"Idempotency-Key": key} if key else {}
        response = await self._client.post(path, json=body, headers=headers)
        await self.assert_reconciled()
        return response


def _product_id(sku: str) -> UUID:
    return seed.PRODUCTS[sku][0]
