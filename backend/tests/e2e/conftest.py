from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.e2e.harness import Warehouse


@pytest.fixture
async def warehouse(client: AsyncClient) -> Warehouse:
    """Склад с тестовым приходом из задания: то же, что видит проверяющий."""
    wh = Warehouse(client)
    await wh.post_test_receipt()
    return wh


@pytest.fixture
def empty_warehouse(client: AsyncClient) -> Warehouse:
    """Справочники есть, остатки нулевые."""
    return Warehouse(client)
