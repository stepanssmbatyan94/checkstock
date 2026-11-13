"""Общая подготовка: отдельная тестовая база в настоящей PostgreSQL.

Тесты учёта не используют подмену базы: блокировки строк, CHECK-ограничения
и транзакции — часть проверяемого поведения.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Тестовая база — соседняя с рабочей, с суффиксом _test.
_main_url = make_url(get_settings().database_url)
TEST_DATABASE_URL = _main_url.set(database=f"{_main_url.database}_test")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL.render_as_string(hide_password=False)
get_settings.cache_clear()

from app import seed  # noqa: E402
from app.infrastructure import tables  # noqa: E402
from app.main import create_app  # noqa: E402


async def _recreate_test_database() -> None:
    admin = create_async_engine(
        TEST_DATABASE_URL.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    async with admin.connect() as connection:
        name = TEST_DATABASE_URL.database
        await connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        await connection.execute(text(f'CREATE DATABASE "{name}"'))
    await admin.dispose()


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    await _recreate_test_database()
    # Схему создаёт та же миграция Alembic, что и в рабочем запуске.
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        check=True,
        env=os.environ,
    )
    engine = create_async_engine(os.environ["DATABASE_URL"])
    yield engine
    await engine.dispose()


@pytest.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """HTTP-клиент к приложению на чистой базе со справочниками из задания."""
    async with engine.begin() as connection:
        table_names = ", ".join(t.name for t in tables.metadata.sorted_tables)
        await connection.execute(text(f"TRUNCATE {table_names} CASCADE"))
    await seed.seed_reference_data(engine)

    app = create_app()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http,
    ):
        yield http
