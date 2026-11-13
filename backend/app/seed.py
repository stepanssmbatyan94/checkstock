"""Тестовые данные из задания: один магазин, два ФФ, три товара и приход.

    python -m app.seed                 справочники + тестовый приход
    python -m app.seed --no-receipts   только справочники, остатки нулевые

Приход проводится теми же командами, что и из интерфейса, поэтому попадает
в историю. Идентификаторы и ключи идемпотентности фиксированы, так что
повторный запуск ничего не дублирует.
"""

from __future__ import annotations

import asyncio
import sys
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import get_settings
from app.infrastructure import tables
from app.main import build_commands

SHOP_ID = UUID("00000000-0000-4000-8000-000000000001")
NORTH_ID = UUID("00000000-0000-4000-8000-000000000011")
SOUTH_ID = UUID("00000000-0000-4000-8000-000000000012")

# Артикул → (id, название, приход на Север, приход на Юг)
PRODUCTS = {
    "SKU-101": (UUID("00000000-0000-4000-8000-000000000101"), "Органайзер", 10, 6),
    "SKU-102": (UUID("00000000-0000-4000-8000-000000000102"), "Контейнер", 5, 0),
    "SKU-103": (UUID("00000000-0000-4000-8000-000000000103"), "Корзина", 0, 4),
}


async def seed_reference_data(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            insert(tables.shops)
            .values(id=SHOP_ID, name="Тестовый магазин")
            .on_conflict_do_nothing()
        )
        for warehouse_id, name in ((NORTH_ID, "Север"), (SOUTH_ID, "Юг")):
            await connection.execute(
                insert(tables.warehouses)
                .values(id=warehouse_id, name=name)
                .on_conflict_do_nothing()
            )
        for sku, (product_id, name, _, _) in PRODUCTS.items():
            await connection.execute(
                insert(tables.products)
                .values(id=product_id, shop_id=SHOP_ID, sku=sku, name=name)
                .on_conflict_do_nothing()
            )


async def seed_receipts(engine: AsyncEngine) -> None:
    commands = build_commands(engine)
    for sku, (product_id, _, north, south) in PRODUCTS.items():
        for warehouse_id, quantity in ((NORTH_ID, north), (SOUTH_ID, south)):
            if quantity > 0:
                await commands.receive_goods(
                    product_id,
                    warehouse_id,
                    quantity,
                    idempotency_key=f"seed:{sku}:{warehouse_id}",
                )


async def main(with_receipts: bool) -> None:
    engine = create_async_engine(get_settings().database_url)
    try:
        await seed_reference_data(engine)
        if with_receipts:
            await seed_receipts(engine)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(with_receipts="--no-receipts" not in sys.argv))
