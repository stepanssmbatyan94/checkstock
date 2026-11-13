"""Схемы запросов и ответов HTTP. Доменные типы сюда не попадают."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class _Response(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Запросы ──────────────────────────────────────────────────────────────


class WarehouseNameRequest(BaseModel):
    name: str


class StockOperationRequest(BaseModel):
    """Приход, резерв FBS и отправка FBO: товар, ФФ, количество."""

    product_id: UUID
    warehouse_id: UUID
    quantity: int


class TransferRequest(BaseModel):
    product_id: UUID
    from_warehouse_id: UUID
    to_warehouse_id: UUID
    quantity: int


# ── Ответы ───────────────────────────────────────────────────────────────


class WarehouseResponse(_Response):
    id: UUID
    name: str
    is_archived: bool
    deleted_at: datetime | None
    on_hand: int
    reserved: int
    incoming: int


class ProductResponse(_Response):
    id: UUID
    sku: str
    name: str


class StockCellResponse(_Response):
    warehouse_id: UUID
    on_hand: int
    reserved: int
    available: int


class StockRowResponse(_Response):
    product_id: UUID
    sku: str
    name: str
    cells: list[StockCellResponse]
    total_on_hand: int
    total_reserved: int
    total_available: int
    in_transit_transfer: int
    in_transit_fbo: int
    in_transit_fbs: int
    at_marketplace: int


class StockOverviewResponse(_Response):
    shop_name: str
    warehouses: list[WarehouseResponse]
    rows: list[StockRowResponse]


class TransferResponse(_Response):
    id: UUID
    sku: str
    product_name: str
    from_warehouse: str
    to_warehouse: str
    quantity: int
    status: str
    shipped_at: datetime
    received_at: datetime | None


class FbsOrderResponse(_Response):
    id: UUID
    sku: str
    product_name: str
    warehouse: str
    quantity: int
    status: str
    reserved_at: datetime
    closed_at: datetime | None


class FboShipmentResponse(_Response):
    id: UUID
    sku: str
    product_name: str
    warehouse: str
    quantity: int
    status: str
    shipped_at: datetime
    accepted_at: datetime | None


class MovementResponse(_Response):
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


class DiscrepancyResponse(_Response):
    account: str
    warehouse_id: UUID | None
    product_id: UUID
    in_ledger: int
    in_balances: int


class ReconciliationResponse(_Response):
    consistent: bool
    discrepancies: list[DiscrepancyResponse]
