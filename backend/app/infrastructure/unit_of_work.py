"""PostgreSQL-реализация портов записи: одна транзакция на операцию."""

from __future__ import annotations

from dataclasses import asdict
from types import TracebackType
from typing import Any
from uuid import UUID

from sqlalchemy import Table, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction

from app.domain import ports
from app.domain.documents import FboShipment, FbsOrder, Transfer
from app.domain.errors import (
    IdempotencyKeyReused,
    NameAlreadyTaken,
    NotFound,
    StockAlternative,
)
from app.domain.ledger import Movement
from app.domain.stock import StockLine
from app.domain.warehouse import Warehouse
from app.infrastructure import tables


class _DocumentRepository[T]:
    """Общий код трёх репозиториев документов: поля датакласса = колонки."""

    table: Table
    entity: type[T]
    not_found_message: str

    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, document: T) -> None:
        await self._connection.execute(self.table.insert().values(asdict(document)))

    async def get_for_update(self, document_id: UUID) -> T:
        # Блокировка документа сериализует повторные подтверждения: второй
        # запрос дождётся первого и увидит уже изменённый статус.
        row = (
            (
                await self._connection.execute(
                    select(self.table)
                    .where(self.table.c.id == document_id)
                    .with_for_update()
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise NotFound(self.not_found_message)
        return self.entity(**row)

    async def save(self, document: T) -> None:
        values = asdict(document)
        document_id = values.pop("id")
        await self._connection.execute(
            update(self.table).where(self.table.c.id == document_id).values(values)
        )


class SqlTransfers(_DocumentRepository[Transfer], ports.TransferRepository):
    table = tables.transfers
    entity = Transfer
    not_found_message = "Перемещение не найдено"


class SqlFbsOrders(_DocumentRepository[FbsOrder], ports.FbsOrderRepository):
    table = tables.fbs_orders
    entity = FbsOrder
    not_found_message = "Заказ FBS не найден"


class SqlFboShipments(_DocumentRepository[FboShipment], ports.FboShipmentRepository):
    table = tables.fbo_shipments
    entity = FboShipment
    not_found_message = "Поставка FBO не найдена"


class SqlWarehouses(ports.WarehouseRepository):
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, warehouse: Warehouse) -> None:
        await self._write(
            tables.warehouses.insert().values(id=warehouse.id, name=warehouse.name)
        )

    async def get(self, warehouse_id: UUID, *, for_update: bool = False) -> Warehouse:
        row = (
            (
                await self._connection.execute(
                    select(
                        tables.warehouses.c.id,
                        tables.warehouses.c.name,
                        tables.warehouses.c.deleted_at,
                    )
                    .where(tables.warehouses.c.id == warehouse_id)
                    .with_for_update(read=not for_update)
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise NotFound("ФФ не найден")
        return Warehouse(**row)

    async def save(self, warehouse: Warehouse) -> None:
        await self._write(
            update(tables.warehouses)
            .where(tables.warehouses.c.id == warehouse.id)
            .values(name=warehouse.name, deleted_at=warehouse.deleted_at)
        )

    async def _write(self, statement: Any) -> None:
        try:
            await self._connection.execute(statement)
        except IntegrityError as error:
            if "uq_warehouses_active_name" in str(error.orig):
                raise NameAlreadyTaken(
                    "Действующий ФФ с таким названием уже есть"
                ) from error
            raise


class SqlProducts(ports.ProductRepository):
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def ensure_exists(self, product_id: UUID) -> None:
        found = await self._connection.scalar(
            select(tables.products.c.id).where(tables.products.c.id == product_id)
        )
        if found is None:
            raise NotFound("Товар не найден")


class SqlStock(ports.StockRepository):
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def get_for_update(self, product_id: UUID, warehouse_id: UUID) -> StockLine:
        # Сначала гарантируем, что строка есть, иначе блокировать нечего:
        # два одновременных первых прихода оба увидели бы «пусто».
        await self._connection.execute(
            insert(tables.stock)
            .values(
                product_id=product_id, warehouse_id=warehouse_id, on_hand=0, reserved=0
            )
            .on_conflict_do_nothing()
        )
        row = (
            (
                await self._connection.execute(
                    select(tables.stock)
                    .where(
                        tables.stock.c.product_id == product_id,
                        tables.stock.c.warehouse_id == warehouse_id,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one()
        )
        return StockLine(**row)

    async def save(self, line: StockLine) -> None:
        await self._connection.execute(
            update(tables.stock)
            .where(
                tables.stock.c.product_id == line.product_id,
                tables.stock.c.warehouse_id == line.warehouse_id,
            )
            .values(on_hand=line.on_hand, reserved=line.reserved)
        )

    async def available_elsewhere(
        self, product_id: UUID, except_warehouse_id: UUID
    ) -> list[StockAlternative]:
        rows = await self._connection.execute(
            text(
                """
                SELECT w.id, w.name, s.on_hand - s.reserved AS available
                FROM stock s
                JOIN warehouses w ON w.id = s.warehouse_id
                WHERE s.product_id = :product_id
                  AND s.warehouse_id <> :except_id
                  AND w.deleted_at IS NULL
                  AND s.on_hand - s.reserved > 0
                ORDER BY available DESC, w.name
                """
            ),
            {"product_id": product_id, "except_id": except_warehouse_id},
        )
        return [StockAlternative(r.id, r.name, r.available) for r in rows]


class SqlJournal(ports.MovementJournal):
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def record(self, movement: Movement) -> None:
        await self._connection.execute(
            tables.movements.insert().values(
                id=movement.id,
                operation=movement.operation,
                product_id=movement.product_id,
                quantity=movement.quantity,
                from_kind=movement.source.kind,
                from_warehouse_id=movement.source.warehouse_id,
                to_kind=movement.destination.kind,
                to_warehouse_id=movement.destination.warehouse_id,
                document_id=movement.document_id,
            )
        )


class SqlIdempotency(ports.IdempotencyStore):
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def claim(self, key: str, fingerprint: str) -> UUID | None:
        # Если параллельная транзакция уже вставила этот ключ, INSERT ждёт её
        # завершения: после коммита увидим готовый результат, после отката —
        # вставим ключ сами.
        claimed = await self._connection.scalar(
            insert(tables.idempotency_keys)
            .values(key=key, fingerprint=fingerprint)
            .on_conflict_do_nothing()
            .returning(tables.idempotency_keys.c.key)
        )
        if claimed is not None:
            return None
        row = (
            await self._connection.execute(
                select(
                    tables.idempotency_keys.c.fingerprint,
                    tables.idempotency_keys.c.result_id,
                ).where(tables.idempotency_keys.c.key == key)
            )
        ).one()
        if row.fingerprint != fingerprint:
            raise IdempotencyKeyReused(
                "Этот ключ идемпотентности уже использован для другой операции"
            )
        return row.result_id

    async def complete(self, key: str, result_id: UUID) -> None:
        await self._connection.execute(
            update(tables.idempotency_keys)
            .where(tables.idempotency_keys.c.key == key)
            .values(result_id=result_id)
        )


class SqlUnitOfWork(ports.UnitOfWork):
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._connection: AsyncConnection
        self._transaction: AsyncTransaction

    async def __aenter__(self) -> SqlUnitOfWork:
        self._connection = await self._engine.connect()
        self._transaction = await self._connection.begin()
        self.warehouses = SqlWarehouses(self._connection)
        self.products = SqlProducts(self._connection)
        self.stock = SqlStock(self._connection)
        self.transfers = SqlTransfers(self._connection)
        self.fbs_orders = SqlFbsOrders(self._connection)
        self.fbo_shipments = SqlFboShipments(self._connection)
        self.journal = SqlJournal(self._connection)
        self.idempotency = SqlIdempotency(self._connection)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if exc_type is None:
                await self._transaction.commit()
            else:
                await self._transaction.rollback()
        finally:
            await self._connection.close()
