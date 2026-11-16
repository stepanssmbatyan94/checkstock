"""Точка сборки: единственное место, где порты соединяются с PostgreSQL."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.api.errors import register_error_handlers
from app.api.router import router
from app.application.commands import InventoryCommands
from app.application.queries import InventoryQueries
from app.config import get_settings
from app.infrastructure.read_model import SqlInventoryReadModel
from app.infrastructure.unit_of_work import SqlUnitOfWork


def build_commands(engine: AsyncEngine) -> InventoryCommands:
    return InventoryCommands(lambda: SqlUnitOfWork(engine))


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_async_engine(get_settings().database_url)
        read_model = SqlInventoryReadModel(engine)
        app.state.commands = build_commands(engine)
        app.state.read_model = read_model
        app.state.queries = InventoryQueries(read_model)
        yield
        await engine.dispose()

    # Документация живёт под /api, чтобы открываться с того же адреса, что и
    # интерфейс: nginx и dev-сервер Vite проксируют /api целиком.
    app = FastAPI(
        title="CheckStock",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    register_error_handlers(app)
    app.include_router(router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
