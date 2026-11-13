"""Операции, меняющие учёт.

Каждый метод открывает одну транзакцию (UnitOfWork) и делает три вещи
вместе: меняет документ, меняет остаток, пишет строку в журнал движений.

Порядок блокировок везде одинаковый — склад, затем документ, затем строка
остатка — и в одной операции блокируется только одна строка остатка,
поэтому взаимных блокировок между операциями не возникает.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

from app.domain.documents import FboShipment, FbsOrder, Transfer
from app.domain.errors import InsufficientStock
from app.domain.ledger import Movement
from app.domain.ports import UnitOfWork
from app.domain.stock import StockLine, ensure_positive
from app.domain.warehouse import Warehouse

UnitOfWorkFactory = Callable[[], UnitOfWork]


def _now() -> datetime:
    return datetime.now(UTC)


class InventoryCommands:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    # ── Склады ───────────────────────────────────────────────────────────

    async def create_warehouse(self, name: str) -> UUID:
        warehouse = Warehouse.create(name)
        async with self._uow_factory() as uow:
            await uow.warehouses.add(warehouse)
        return warehouse.id

    async def rename_warehouse(self, warehouse_id: UUID, name: str) -> None:
        async with self._uow_factory() as uow:
            warehouse = await uow.warehouses.get(warehouse_id, for_update=True)
            warehouse.rename(name)
            await uow.warehouses.save(warehouse)

    async def archive_warehouse(self, warehouse_id: UUID) -> None:
        """Удаление ФФ. Остатки, документы и журнал не трогаем вообще:
        товар продолжает числиться на архивном складе."""
        async with self._uow_factory() as uow:
            warehouse = await uow.warehouses.get(warehouse_id, for_update=True)
            if warehouse.archive(_now()):
                await uow.warehouses.save(warehouse)

    # ── Приход ───────────────────────────────────────────────────────────

    async def receive_goods(
        self,
        product_id: UUID,
        warehouse_id: UUID,
        quantity: int,
        idempotency_key: str | None = None,
    ) -> UUID:
        """Возвращает id записи журнала."""
        ensure_positive(quantity)
        fingerprint = f"receipt:{product_id}:{warehouse_id}:{quantity}"

        async with self._uow_factory() as uow:

            async def action() -> UUID:
                await uow.products.ensure_exists(product_id)
                (await uow.warehouses.get(warehouse_id)).ensure_active()
                line = await uow.stock.get_for_update(product_id, warehouse_id)
                line.receive(quantity)
                await uow.stock.save(line)
                movement = Movement.receipt(product_id, warehouse_id, quantity)
                await uow.journal.record(movement)
                return movement.id

            return await _once(uow, idempotency_key, fingerprint, action)

    # ── Перемещения между ФФ ─────────────────────────────────────────────

    async def ship_transfer(
        self,
        product_id: UUID,
        from_warehouse_id: UUID,
        to_warehouse_id: UUID,
        quantity: int,
        idempotency_key: str | None = None,
    ) -> UUID:
        fingerprint = (
            f"transfer:{product_id}:{from_warehouse_id}:{to_warehouse_id}:{quantity}"
        )

        async with self._uow_factory() as uow:

            async def action() -> UUID:
                transfer = Transfer.ship(
                    product_id, from_warehouse_id, to_warehouse_id, quantity, _now()
                )
                await uow.products.ensure_exists(product_id)
                # Вывезти товар можно и с удалённого ФФ — иначе остаток на нём
                # застрянет навсегда. Привезти на удалённый нельзя.
                await uow.warehouses.get(from_warehouse_id)
                (await uow.warehouses.get(to_warehouse_id)).ensure_active()

                line = await uow.stock.get_for_update(product_id, from_warehouse_id)
                await _take_available(uow, line, quantity)
                await uow.stock.save(line)
                await uow.transfers.add(transfer)
                await uow.journal.record(
                    Movement.transfer_shipped(
                        transfer.id,
                        product_id,
                        from_warehouse_id,
                        to_warehouse_id,
                        quantity,
                    )
                )
                return transfer.id

            return await _once(uow, idempotency_key, fingerprint, action)

    async def receive_transfer(self, transfer_id: UUID) -> None:
        async with self._uow_factory() as uow:
            transfer = await uow.transfers.get_for_update(transfer_id)
            if not transfer.receive(_now()):
                return  # уже принято: повтор ничего не меняет
            # Склад назначения не проверяем на архив: товар уже в пути,
            # и отказ в приёмке оставил бы его висеть в транзите.
            line = await uow.stock.get_for_update(
                transfer.product_id, transfer.to_warehouse_id
            )
            line.receive(transfer.quantity)
            await uow.stock.save(line)
            await uow.transfers.save(transfer)
            await uow.journal.record(
                Movement.transfer_received(
                    transfer.id,
                    transfer.product_id,
                    transfer.to_warehouse_id,
                    transfer.quantity,
                )
            )

    # ── FBS: резерв → отправка клиенту или отмена ────────────────────────

    async def reserve_fbs(
        self,
        product_id: UUID,
        warehouse_id: UUID,
        quantity: int,
        idempotency_key: str | None = None,
    ) -> UUID:
        fingerprint = f"fbs:{product_id}:{warehouse_id}:{quantity}"

        async with self._uow_factory() as uow:

            async def action() -> UUID:
                order = FbsOrder.reserve(product_id, warehouse_id, quantity, _now())
                await uow.products.ensure_exists(product_id)
                (await uow.warehouses.get(warehouse_id)).ensure_active()

                line = await uow.stock.get_for_update(product_id, warehouse_id)
                try:
                    line.reserve(quantity)
                except InsufficientStock as shortage:
                    await _attach_alternatives(uow, shortage)
                    raise
                await uow.stock.save(line)
                await uow.fbs_orders.add(order)
                await uow.journal.record(
                    Movement.fbs_reserved(order.id, product_id, warehouse_id, quantity)
                )
                return order.id

            return await _once(uow, idempotency_key, fingerprint, action)

    async def ship_fbs(self, order_id: UUID) -> None:
        async with self._uow_factory() as uow:
            order = await uow.fbs_orders.get_for_update(order_id)
            if not order.ship(_now()):
                return  # уже отправлен: второй раз товар не списываем
            line = await uow.stock.get_for_update(order.product_id, order.warehouse_id)
            line.ship_reserved(order.quantity)
            await uow.stock.save(line)
            await uow.fbs_orders.save(order)
            await uow.journal.record(
                Movement.fbs_shipped(
                    order.id, order.product_id, order.warehouse_id, order.quantity
                )
            )

    async def cancel_fbs(self, order_id: UUID) -> None:
        async with self._uow_factory() as uow:
            order = await uow.fbs_orders.get_for_update(order_id)
            if not order.cancel(_now()):
                return  # уже отменён: резерв второй раз не возвращаем
            line = await uow.stock.get_for_update(order.product_id, order.warehouse_id)
            line.release(order.quantity)
            await uow.stock.save(line)
            await uow.fbs_orders.save(order)
            await uow.journal.record(
                Movement.fbs_cancelled(
                    order.id, order.product_id, order.warehouse_id, order.quantity
                )
            )

    # ── FBO: отправка на склад маркетплейса → приёмка ────────────────────

    async def ship_fbo(
        self,
        product_id: UUID,
        warehouse_id: UUID,
        quantity: int,
        idempotency_key: str | None = None,
    ) -> UUID:
        fingerprint = f"fbo:{product_id}:{warehouse_id}:{quantity}"

        async with self._uow_factory() as uow:

            async def action() -> UUID:
                shipment = FboShipment.ship(product_id, warehouse_id, quantity, _now())
                await uow.products.ensure_exists(product_id)
                (await uow.warehouses.get(warehouse_id)).ensure_active()

                line = await uow.stock.get_for_update(product_id, warehouse_id)
                await _take_available(uow, line, quantity)
                await uow.stock.save(line)
                await uow.fbo_shipments.add(shipment)
                await uow.journal.record(
                    Movement.fbo_shipped(
                        shipment.id, product_id, warehouse_id, quantity
                    )
                )
                return shipment.id

            return await _once(uow, idempotency_key, fingerprint, action)

    async def accept_fbo(self, shipment_id: UUID) -> None:
        async with self._uow_factory() as uow:
            shipment = await uow.fbo_shipments.get_for_update(shipment_id)
            if not shipment.accept(_now()):
                return  # уже принято маркетплейсом
            await uow.fbo_shipments.save(shipment)
            await uow.journal.record(
                Movement.fbo_accepted(
                    shipment.id, shipment.product_id, shipment.quantity
                )
            )


async def _once(
    uow: UnitOfWork,
    key: str | None,
    fingerprint: str,
    action: Callable[[], Awaitable[UUID]],
) -> UUID:
    """Выполняет создающую операцию не более одного раза на ключ.

    Ключ занимается в той же транзакции, что и сама операция. Повторный
    запрос с тем же ключом (двойной клик, повтор после обрыва сети) получает
    id уже созданного документа и ничего не меняет в учёте. Если операция
    упала, транзакция откатывается вместе с ключом — её можно повторить.
    """
    if key is None:
        return await action()
    existing = await uow.idempotency.claim(key, fingerprint)
    if existing is not None:
        return existing
    result_id = await action()
    await uow.idempotency.complete(key, result_id)
    return result_id


async def _take_available(uow: UnitOfWork, line: StockLine, quantity: int) -> None:
    try:
        line.ship_available(quantity)
    except InsufficientStock as shortage:
        await _attach_alternatives(uow, shortage)
        raise


async def _attach_alternatives(uow: UnitOfWork, shortage: InsufficientStock) -> None:
    shortage.alternatives = await uow.stock.available_elsewhere(
        shortage.product_id, except_warehouse_id=shortage.warehouse_id
    )
