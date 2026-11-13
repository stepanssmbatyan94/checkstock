"""HTTP-маршруты: запрос → команда или чтение → ответ. Логики учёта здесь нет."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request

from app.api import schemas
from app.application.commands import InventoryCommands
from app.application.queries import InventoryQueries, InventoryReadModel

router = APIRouter(prefix="/api")


def _commands(request: Request) -> InventoryCommands:
    return request.app.state.commands


def _queries(request: Request) -> InventoryQueries:
    return request.app.state.queries


def _read(request: Request) -> InventoryReadModel:
    return request.app.state.read_model


Commands = Annotated[InventoryCommands, Depends(_commands)]
Queries = Annotated[InventoryQueries, Depends(_queries)]
Read = Annotated[InventoryReadModel, Depends(_read)]
# Клиент присылает свой ключ для операций, которые создают документ.
# Повтор запроса с тем же ключом возвращает тот же документ.
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key")]


# ── Остатки и сверка ─────────────────────────────────────────────────────


@router.get("/stock", response_model=schemas.StockOverviewResponse)
async def stock_overview(queries: Queries):
    return await queries.stock_overview()


@router.get("/reconciliation", response_model=schemas.ReconciliationResponse)
async def reconciliation(queries: Queries):
    return await queries.reconciliation()


@router.get("/products", response_model=list[schemas.ProductResponse])
async def list_products(read: Read):
    return await read.products()


@router.get("/movements", response_model=list[schemas.MovementResponse])
async def list_movements(read: Read, limit: Annotated[int, Query(ge=1, le=500)] = 200):
    return await read.movements(limit)


# ── Склады ───────────────────────────────────────────────────────────────


@router.get("/warehouses", response_model=list[schemas.WarehouseResponse])
async def list_warehouses(read: Read):
    return await read.warehouses()


@router.post("/warehouses", response_model=schemas.WarehouseResponse, status_code=201)
async def create_warehouse(
    body: schemas.WarehouseNameRequest, commands: Commands, read: Read
):
    return await read.warehouse(await commands.create_warehouse(body.name))


@router.patch("/warehouses/{warehouse_id}", response_model=schemas.WarehouseResponse)
async def rename_warehouse(
    warehouse_id: UUID,
    body: schemas.WarehouseNameRequest,
    commands: Commands,
    read: Read,
):
    await commands.rename_warehouse(warehouse_id, body.name)
    return await read.warehouse(warehouse_id)


@router.delete("/warehouses/{warehouse_id}", response_model=schemas.WarehouseResponse)
async def delete_warehouse(warehouse_id: UUID, commands: Commands, read: Read):
    """Удаление = архив. В ответе видно, что продолжает числиться на складе."""
    await commands.archive_warehouse(warehouse_id)
    return await read.warehouse(warehouse_id)


# ── Приход ───────────────────────────────────────────────────────────────


@router.post("/receipts", response_model=schemas.MovementResponse, status_code=201)
async def receive_goods(
    body: schemas.StockOperationRequest,
    commands: Commands,
    read: Read,
    idempotency_key: IdempotencyKey = None,
):
    movement_id = await commands.receive_goods(
        body.product_id, body.warehouse_id, body.quantity, idempotency_key
    )
    return await read.movement(movement_id)


# ── Перемещения между ФФ ─────────────────────────────────────────────────


@router.get("/transfers", response_model=list[schemas.TransferResponse])
async def list_transfers(read: Read):
    return await read.transfers()


@router.post("/transfers", response_model=schemas.TransferResponse, status_code=201)
async def ship_transfer(
    body: schemas.TransferRequest,
    commands: Commands,
    read: Read,
    idempotency_key: IdempotencyKey = None,
):
    transfer_id = await commands.ship_transfer(
        body.product_id,
        body.from_warehouse_id,
        body.to_warehouse_id,
        body.quantity,
        idempotency_key,
    )
    return await read.transfer(transfer_id)


@router.post(
    "/transfers/{transfer_id}/receive", response_model=schemas.TransferResponse
)
async def receive_transfer(transfer_id: UUID, commands: Commands, read: Read):
    await commands.receive_transfer(transfer_id)
    return await read.transfer(transfer_id)


# ── FBS ──────────────────────────────────────────────────────────────────


@router.get("/fbs-orders", response_model=list[schemas.FbsOrderResponse])
async def list_fbs_orders(read: Read):
    return await read.fbs_orders()


@router.post("/fbs-orders", response_model=schemas.FbsOrderResponse, status_code=201)
async def reserve_fbs(
    body: schemas.StockOperationRequest,
    commands: Commands,
    read: Read,
    idempotency_key: IdempotencyKey = None,
):
    order_id = await commands.reserve_fbs(
        body.product_id, body.warehouse_id, body.quantity, idempotency_key
    )
    return await read.fbs_order(order_id)


@router.post("/fbs-orders/{order_id}/ship", response_model=schemas.FbsOrderResponse)
async def ship_fbs(order_id: UUID, commands: Commands, read: Read):
    await commands.ship_fbs(order_id)
    return await read.fbs_order(order_id)


@router.post("/fbs-orders/{order_id}/cancel", response_model=schemas.FbsOrderResponse)
async def cancel_fbs(order_id: UUID, commands: Commands, read: Read):
    await commands.cancel_fbs(order_id)
    return await read.fbs_order(order_id)


# ── FBO ──────────────────────────────────────────────────────────────────


@router.get("/fbo-shipments", response_model=list[schemas.FboShipmentResponse])
async def list_fbo_shipments(read: Read):
    return await read.fbo_shipments()


@router.post(
    "/fbo-shipments", response_model=schemas.FboShipmentResponse, status_code=201
)
async def ship_fbo(
    body: schemas.StockOperationRequest,
    commands: Commands,
    read: Read,
    idempotency_key: IdempotencyKey = None,
):
    shipment_id = await commands.ship_fbo(
        body.product_id, body.warehouse_id, body.quantity, idempotency_key
    )
    return await read.fbo_shipment(shipment_id)


@router.post(
    "/fbo-shipments/{shipment_id}/accept", response_model=schemas.FboShipmentResponse
)
async def accept_fbo(shipment_id: UUID, commands: Commands, read: Read):
    await commands.accept_fbo(shipment_id)
    return await read.fbo_shipment(shipment_id)
