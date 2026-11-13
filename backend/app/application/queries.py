"""Чтение: модели для экранов, порт чтения и сверка учёта."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# Ключ счёта при сверке: (вид счёта, склад или None, товар).
BalanceKey = tuple[str, UUID | None, UUID]
Balances = dict[BalanceKey, int]


@dataclass(frozen=True)
class WarehouseView:
    id: UUID
    name: str
    is_archived: bool
    deleted_at: datetime | None
    # Что числится на складе: нужно, чтобы показать это при удалении.
    on_hand: int
    reserved: int
    incoming: int  # едет на этот ФФ перемещениями


@dataclass(frozen=True)
class ProductView:
    id: UUID
    sku: str
    name: str


@dataclass(frozen=True)
class StockCell:
    warehouse_id: UUID
    on_hand: int
    reserved: int
    available: int


@dataclass(frozen=True)
class StockRow:
    product_id: UUID
    sku: str
    name: str
    cells: list[StockCell]
    total_on_hand: int
    total_reserved: int
    total_available: int  # только на действующих ФФ
    in_transit_transfer: int
    in_transit_fbo: int
    in_transit_fbs: int
    at_marketplace: int


@dataclass(frozen=True)
class StockOverview:
    shop_name: str
    warehouses: list[WarehouseView]
    rows: list[StockRow]


@dataclass(frozen=True)
class TransferView:
    id: UUID
    sku: str
    product_name: str
    from_warehouse: str
    to_warehouse: str
    quantity: int
    status: str
    shipped_at: datetime
    received_at: datetime | None


@dataclass(frozen=True)
class FbsOrderView:
    id: UUID
    sku: str
    product_name: str
    warehouse: str
    quantity: int
    status: str
    reserved_at: datetime
    closed_at: datetime | None


@dataclass(frozen=True)
class FboShipmentView:
    id: UUID
    sku: str
    product_name: str
    warehouse: str
    quantity: int
    status: str
    shipped_at: datetime
    accepted_at: datetime | None


@dataclass(frozen=True)
class MovementView:
    id: UUID
    created_at: datetime
    operation: str
    sku: str
    product_name: str
    quantity: int
    from_kind: str
    from_warehouse: str | None
    to_kind: str
    to_warehouse: str | None
    document_id: UUID | None


@dataclass(frozen=True)
class StockFact:
    product_id: UUID
    warehouse_id: UUID
    on_hand: int
    reserved: int


@dataclass(frozen=True)
class Discrepancy:
    account: str
    warehouse_id: UUID | None
    product_id: UUID
    in_ledger: int
    in_balances: int


@dataclass(frozen=True)
class Reconciliation:
    consistent: bool
    discrepancies: list[Discrepancy]


class InventoryReadModel(ABC):
    @abstractmethod
    def snapshot(self) -> AbstractAsyncContextManager[InventoryReadModel]:
        """Чтение на один момент времени.

        Экран остатков и сверка собираются из нескольких запросов. Без
        общего снимка между ними может зафиксироваться чужая операция, и
        картина выйдет несогласованной, хотя сам учёт верен.
        """

    @abstractmethod
    async def shop_name(self) -> str: ...

    @abstractmethod
    async def warehouses(self) -> list[WarehouseView]: ...

    @abstractmethod
    async def warehouse(self, warehouse_id: UUID) -> WarehouseView: ...

    @abstractmethod
    async def products(self) -> list[ProductView]: ...

    @abstractmethod
    async def stock_facts(self) -> list[StockFact]: ...

    @abstractmethod
    async def transfers(self) -> list[TransferView]: ...

    @abstractmethod
    async def transfer(self, transfer_id: UUID) -> TransferView: ...

    @abstractmethod
    async def fbs_orders(self) -> list[FbsOrderView]: ...

    @abstractmethod
    async def fbs_order(self, order_id: UUID) -> FbsOrderView: ...

    @abstractmethod
    async def fbo_shipments(self) -> list[FboShipmentView]: ...

    @abstractmethod
    async def fbo_shipment(self, shipment_id: UUID) -> FboShipmentView: ...

    @abstractmethod
    async def movements(self, limit: int) -> list[MovementView]: ...

    @abstractmethod
    async def movement(self, movement_id: UUID) -> MovementView: ...

    @abstractmethod
    async def ledger_balances(self) -> Balances:
        """Остатки по счетам, пересчитанные из журнала движений."""

    @abstractmethod
    async def projected_balances(self) -> Balances:
        """Те же счета из рабочих таблиц: остатки на ФФ и документы в пути."""


class InventoryQueries:
    def __init__(self, read_model: InventoryReadModel) -> None:
        self._read = read_model

    async def stock_overview(self) -> StockOverview:
        async with self._read.snapshot() as read:
            shop_name = await read.shop_name()
            all_warehouses = await read.warehouses()
            products = await read.products()
            stock_facts = await read.stock_facts()
            projected = await read.projected_balances()

        # Удалённый ФФ остаётся на экране, пока на нём что-то числится
        # или к нему что-то едет. Пустой архивный склад не показываем.
        shown = [
            w
            for w in all_warehouses
            if not w.is_archived or w.on_hand > 0 or w.incoming > 0
        ]
        active_ids = {w.id for w in all_warehouses if not w.is_archived}
        facts = {(f.product_id, f.warehouse_id): f for f in stock_facts}

        def in_account(kind: str, product_id: UUID) -> int:
            return sum(
                quantity
                for (account, _, product), quantity in projected.items()
                if account == kind and product == product_id
            )

        rows: list[StockRow] = []
        for product in products:
            cells: list[StockCell] = []
            for warehouse in shown:
                fact = facts.get((product.id, warehouse.id))
                on_hand = fact.on_hand if fact else 0
                reserved = fact.reserved if fact else 0
                cells.append(
                    StockCell(warehouse.id, on_hand, reserved, on_hand - reserved)
                )
            rows.append(
                StockRow(
                    product_id=product.id,
                    sku=product.sku,
                    name=product.name,
                    cells=cells,
                    total_on_hand=sum(c.on_hand for c in cells),
                    total_reserved=sum(c.reserved for c in cells),
                    total_available=sum(
                        c.available for c in cells if c.warehouse_id in active_ids
                    ),
                    in_transit_transfer=in_account("transit_transfer", product.id),
                    in_transit_fbo=in_account("transit_fbo", product.id),
                    in_transit_fbs=in_account("transit_fbs", product.id),
                    at_marketplace=in_account("marketplace", product.id),
                )
            )
        return StockOverview(shop_name, shown, rows)

    async def reconciliation(self) -> Reconciliation:
        """Сверяет журнал движений с рабочими таблицами.

        Если хоть один счёт расходится, значит какая-то операция изменила
        остаток мимо журнала (или наоборот) — это ошибка учёта.
        """
        async with self._read.snapshot() as read:
            ledger = await read.ledger_balances()
            projected = await read.projected_balances()
        discrepancies = [
            Discrepancy(
                account=key[0],
                warehouse_id=key[1],
                product_id=key[2],
                in_ledger=ledger.get(key, 0),
                in_balances=projected.get(key, 0),
            )
            for key in sorted(ledger.keys() | projected.keys(), key=str)
            if ledger.get(key, 0) != projected.get(key, 0)
        ]
        return Reconciliation(consistent=not discrepancies, discrepancies=discrepancies)
