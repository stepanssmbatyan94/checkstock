"""Порты: что домену и приложению нужно от хранилища.

Реализация на PostgreSQL лежит в `app/infrastructure`. Домен и слой
приложения о SQLAlchemy не знают — это проверяет import-linter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from uuid import UUID

from app.domain.documents import FboShipment, FbsOrder, Transfer
from app.domain.errors import StockAlternative
from app.domain.ledger import Movement
from app.domain.stock import StockLine
from app.domain.warehouse import Warehouse


class WarehouseRepository(ABC):
    @abstractmethod
    async def add(self, warehouse: Warehouse) -> None: ...

    @abstractmethod
    async def get(self, warehouse_id: UUID, *, for_update: bool = False) -> Warehouse:
        """Читает ФФ под блокировкой строки.

        for_update=False берёт разделяемую блокировку: операция со складом
        не даст параллельно его удалить, но не мешает другим операциям.
        """

    @abstractmethod
    async def save(self, warehouse: Warehouse) -> None: ...


class ProductRepository(ABC):
    @abstractmethod
    async def ensure_exists(self, product_id: UUID) -> None: ...


class StockRepository(ABC):
    @abstractmethod
    async def get_for_update(self, product_id: UUID, warehouse_id: UUID) -> StockLine:
        """Блокирует строку остатка до конца транзакции (SELECT … FOR UPDATE)."""

    @abstractmethod
    async def save(self, line: StockLine) -> None: ...

    @abstractmethod
    async def available_elsewhere(
        self, product_id: UUID, except_warehouse_id: UUID
    ) -> list[StockAlternative]:
        """Действующие ФФ, где этот товар есть в доступном остатке."""


class TransferRepository(ABC):
    @abstractmethod
    async def add(self, transfer: Transfer) -> None: ...

    @abstractmethod
    async def get_for_update(self, transfer_id: UUID) -> Transfer: ...

    @abstractmethod
    async def save(self, transfer: Transfer) -> None: ...


class FbsOrderRepository(ABC):
    @abstractmethod
    async def add(self, order: FbsOrder) -> None: ...

    @abstractmethod
    async def get_for_update(self, order_id: UUID) -> FbsOrder: ...

    @abstractmethod
    async def save(self, order: FbsOrder) -> None: ...


class FboShipmentRepository(ABC):
    @abstractmethod
    async def add(self, shipment: FboShipment) -> None: ...

    @abstractmethod
    async def get_for_update(self, shipment_id: UUID) -> FboShipment: ...

    @abstractmethod
    async def save(self, shipment: FboShipment) -> None: ...


class MovementJournal(ABC):
    @abstractmethod
    async def record(self, movement: Movement) -> None: ...


class IdempotencyStore(ABC):
    @abstractmethod
    async def claim(self, key: str, fingerprint: str) -> UUID | None:
        """Занимает ключ. Возвращает id результата, если операция с этим
        ключом уже выполнена, иначе None."""

    @abstractmethod
    async def complete(self, key: str, result_id: UUID) -> None: ...


class UnitOfWork(ABC):
    """Одна бизнес-операция = одна транзакция.

    Изменение остатка, документа и запись в журнал либо фиксируются
    вместе, либо вместе откатываются при любой ошибке.
    """

    warehouses: WarehouseRepository
    products: ProductRepository
    stock: StockRepository
    transfers: TransferRepository
    fbs_orders: FbsOrderRepository
    fbo_shipments: FboShipmentRepository
    journal: MovementJournal
    idempotency: IdempotencyStore

    @abstractmethod
    async def __aenter__(self) -> UnitOfWork: ...

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
