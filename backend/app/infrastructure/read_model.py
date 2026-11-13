"""PostgreSQL-реализация порта чтения. Запросы написаны на SQL как есть."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.application.queries import (
    Balances,
    FboShipmentView,
    FbsOrderView,
    InventoryReadModel,
    MovementView,
    ProductView,
    StockFact,
    TransferView,
    WarehouseView,
)
from app.domain.errors import NotFound

_WAREHOUSES = """
    SELECT w.id, w.name, w.deleted_at IS NOT NULL AS is_archived, w.deleted_at,
           COALESCE((SELECT sum(s.on_hand) FROM stock s
                     WHERE s.warehouse_id = w.id), 0) AS on_hand,
           COALESCE((SELECT sum(s.reserved) FROM stock s
                     WHERE s.warehouse_id = w.id), 0) AS reserved,
           COALESCE((SELECT sum(t.quantity) FROM transfers t
                     WHERE t.to_warehouse_id = w.id
                       AND t.status = 'shipped'), 0) AS incoming
    FROM warehouses w
"""

_TRANSFERS = """
    SELECT t.id, p.sku, p.name AS product_name,
           wf.name AS from_warehouse, wt.name AS to_warehouse,
           t.quantity, t.status, t.shipped_at, t.received_at
    FROM transfers t
    JOIN products p ON p.id = t.product_id
    JOIN warehouses wf ON wf.id = t.from_warehouse_id
    JOIN warehouses wt ON wt.id = t.to_warehouse_id
"""

_FBS_ORDERS = """
    SELECT o.id, p.sku, p.name AS product_name, w.name AS warehouse,
           o.quantity, o.status, o.reserved_at, o.closed_at
    FROM fbs_orders o
    JOIN products p ON p.id = o.product_id
    JOIN warehouses w ON w.id = o.warehouse_id
"""

_FBO_SHIPMENTS = """
    SELECT f.id, p.sku, p.name AS product_name, w.name AS warehouse,
           f.quantity, f.status, f.shipped_at, f.accepted_at
    FROM fbo_shipments f
    JOIN products p ON p.id = f.product_id
    JOIN warehouses w ON w.id = f.warehouse_id
"""

_MOVEMENTS = """
    SELECT m.id, m.created_at, m.operation, p.sku, p.name AS product_name,
           m.quantity, m.from_kind, wf.name AS from_warehouse,
           m.to_kind, wt.name AS to_warehouse, m.document_id
    FROM movements m
    JOIN products p ON p.id = m.product_id
    LEFT JOIN warehouses wf ON wf.id = m.from_warehouse_id
    LEFT JOIN warehouses wt ON wt.id = m.to_warehouse_id
"""

# Каждая строка журнала даёт плюс счёту-получателю и минус счёту-источнику.
# Счёт поставщика — внешний мир, его баланс не сверяем.
_LEDGER_BALANCES = """
    SELECT kind, warehouse_id, product_id, sum(delta)::int AS quantity
    FROM (
        SELECT to_kind AS kind, to_warehouse_id AS warehouse_id,
               product_id, quantity AS delta
        FROM movements
        UNION ALL
        SELECT from_kind, from_warehouse_id, product_id, -quantity
        FROM movements
    ) entries
    WHERE kind <> 'supplier'
    GROUP BY kind, warehouse_id, product_id
    HAVING sum(delta) <> 0
"""

# Те же счета, но из рабочих таблиц. Резерв берём из открытых заказов FBS,
# а «доступно» — из таблицы остатков: так сверка ловит и расхождение между
# stock.reserved и суммой заказов.
_PROJECTED_BALANCES = """
    SELECT 'warehouse_available' AS kind, warehouse_id, product_id,
           on_hand - reserved AS quantity
    FROM stock
    WHERE on_hand - reserved <> 0
    UNION ALL
    SELECT 'warehouse_reserved', warehouse_id, product_id, sum(quantity)::int
    FROM fbs_orders WHERE status = 'reserved'
    GROUP BY warehouse_id, product_id
    UNION ALL
    SELECT 'transit_transfer', to_warehouse_id, product_id, sum(quantity)::int
    FROM transfers WHERE status = 'shipped'
    GROUP BY to_warehouse_id, product_id
    UNION ALL
    SELECT 'transit_fbs', NULL, product_id, sum(quantity)::int
    FROM fbs_orders WHERE status = 'shipped'
    GROUP BY product_id
    UNION ALL
    SELECT 'transit_fbo', NULL, product_id, sum(quantity)::int
    FROM fbo_shipments WHERE status = 'in_transit'
    GROUP BY product_id
    UNION ALL
    SELECT 'marketplace', NULL, product_id, sum(quantity)::int
    FROM fbo_shipments WHERE status = 'accepted'
    GROUP BY product_id
"""


class SqlInventoryReadModel(InventoryReadModel):
    def __init__(
        self, engine: AsyncEngine, snapshot: AsyncConnection | None = None
    ) -> None:
        self._engine = engine
        self._snapshot = snapshot

    @asynccontextmanager
    async def snapshot(self) -> AsyncIterator[SqlInventoryReadModel]:
        # REPEATABLE READ: все запросы внутри видят базу на один и тот же
        # момент, даже если параллельно фиксируются другие операции.
        async with self._engine.connect() as connection:
            await connection.execution_options(isolation_level="REPEATABLE READ")
            async with connection.begin():
                yield SqlInventoryReadModel(self._engine, connection)

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[AsyncConnection]:
        if self._snapshot is not None:
            yield self._snapshot
        else:
            async with self._engine.connect() as connection:
                yield connection

    async def _all[T](
        self, view: type[T], sql: str, params: dict[str, Any] | None = None
    ) -> list[T]:
        async with self._connect() as connection:
            rows = await connection.execute(text(sql), params or {})
            return [view(**row) for row in rows.mappings()]

    async def _one[T](
        self, view: type[T], sql: str, entity_id: UUID, not_found: str
    ) -> T:
        found = await self._all(view, sql, {"id": entity_id})
        if not found:
            raise NotFound(not_found)
        return found[0]

    async def shop_name(self) -> str:
        async with self._connect() as connection:
            name = await connection.scalar(text("SELECT name FROM shops LIMIT 1"))
        return name or ""

    async def warehouses(self) -> list[WarehouseView]:
        return await self._all(
            WarehouseView, _WAREHOUSES + " ORDER BY w.created_at, w.name"
        )

    async def warehouse(self, warehouse_id: UUID) -> WarehouseView:
        return await self._one(
            WarehouseView,
            _WAREHOUSES + " WHERE w.id = :id",
            warehouse_id,
            "ФФ не найден",
        )

    async def products(self) -> list[ProductView]:
        return await self._all(
            ProductView, "SELECT id, sku, name FROM products ORDER BY sku"
        )

    async def stock_facts(self) -> list[StockFact]:
        return await self._all(
            StockFact, "SELECT product_id, warehouse_id, on_hand, reserved FROM stock"
        )

    async def transfers(self) -> list[TransferView]:
        return await self._all(TransferView, _TRANSFERS + " ORDER BY t.shipped_at DESC")

    async def transfer(self, transfer_id: UUID) -> TransferView:
        return await self._one(
            TransferView,
            _TRANSFERS + " WHERE t.id = :id",
            transfer_id,
            "Перемещение не найдено",
        )

    async def fbs_orders(self) -> list[FbsOrderView]:
        return await self._all(
            FbsOrderView, _FBS_ORDERS + " ORDER BY o.reserved_at DESC"
        )

    async def fbs_order(self, order_id: UUID) -> FbsOrderView:
        return await self._one(
            FbsOrderView,
            _FBS_ORDERS + " WHERE o.id = :id",
            order_id,
            "Заказ FBS не найден",
        )

    async def fbo_shipments(self) -> list[FboShipmentView]:
        return await self._all(
            FboShipmentView, _FBO_SHIPMENTS + " ORDER BY f.shipped_at DESC"
        )

    async def fbo_shipment(self, shipment_id: UUID) -> FboShipmentView:
        return await self._one(
            FboShipmentView,
            _FBO_SHIPMENTS + " WHERE f.id = :id",
            shipment_id,
            "Поставка FBO не найдена",
        )

    async def movements(self, limit: int) -> list[MovementView]:
        return await self._all(
            MovementView,
            _MOVEMENTS + " ORDER BY m.seq DESC LIMIT :limit",
            {"limit": limit},
        )

    async def movement(self, movement_id: UUID) -> MovementView:
        return await self._one(
            MovementView,
            _MOVEMENTS + " WHERE m.id = :id",
            movement_id,
            "Запись журнала не найдена",
        )

    async def ledger_balances(self) -> Balances:
        return await self._balances(_LEDGER_BALANCES)

    async def projected_balances(self) -> Balances:
        return await self._balances(_PROJECTED_BALANCES)

    async def _balances(self, sql: str) -> Balances:
        async with self._connect() as connection:
            rows = await connection.execute(text(sql))
            return {
                (row.kind, row.warehouse_id, row.product_id): row.quantity
                for row in rows
            }
