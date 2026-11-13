"""Перевод ошибок предметной области в HTTP-ответы.

Формат один для всех ошибок: {"code", "message", "details"}. Интерфейс
ветвится по `code`, а не по тексту сообщения.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.errors import (
    DomainError,
    InsufficientStock,
    NotFound,
    ValidationFailed,
)


def _details(error: DomainError) -> dict[str, Any]:
    if isinstance(error, InsufficientStock):
        return {
            "requested": error.requested,
            "available": error.available,
            "available_elsewhere": error.available_elsewhere,
            "alternatives": [
                {
                    "warehouse_id": str(a.warehouse_id),
                    "warehouse_name": a.warehouse_name,
                    "available": a.available,
                }
                for a in error.alternatives
            ],
        }
    return {}


def _status(error: DomainError) -> int:
    if isinstance(error, NotFound):
        return 404
    if isinstance(error, ValidationFailed):
        return 422
    # Нехватка, архивный ФФ, недопустимый переход, занятое имя, чужой ключ —
    # запрос корректен, но противоречит текущему состоянию учёта.
    return 409


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, error: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=_status(error),
            content={
                "code": error.code,
                "message": error.message,
                "details": _details(error),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_malformed_request(
        _: Request, error: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_failed",
                "message": "Некорректные данные запроса",
                "details": {"errors": [e["msg"] for e in error.errors()]},
            },
        )
