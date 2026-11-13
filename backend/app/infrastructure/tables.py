"""Описание таблиц для SQLAlchemy Core. Сама схема создаётся миграцией Alembic."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    Uuid,
)

metadata = MetaData()

shops = Table(
    "shops",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("name", Text, nullable=False),
)

products = Table(
    "products",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("shop_id", Uuid, ForeignKey("shops.id"), nullable=False),
    Column("sku", Text, nullable=False, unique=True),
    Column("name", Text, nullable=False),
)

warehouses = Table(
    "warehouses",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("name", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True)),
)

stock = Table(
    "stock",
    metadata,
    Column("product_id", Uuid, ForeignKey("products.id"), primary_key=True),
    Column("warehouse_id", Uuid, ForeignKey("warehouses.id"), primary_key=True),
    Column("on_hand", Integer, nullable=False),
    Column("reserved", Integer, nullable=False),
)

transfers = Table(
    "transfers",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("product_id", Uuid, ForeignKey("products.id"), nullable=False),
    Column("from_warehouse_id", Uuid, ForeignKey("warehouses.id"), nullable=False),
    Column("to_warehouse_id", Uuid, ForeignKey("warehouses.id"), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("status", Text, nullable=False),
    Column("shipped_at", DateTime(timezone=True), nullable=False),
    Column("received_at", DateTime(timezone=True)),
)

fbs_orders = Table(
    "fbs_orders",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("product_id", Uuid, ForeignKey("products.id"), nullable=False),
    Column("warehouse_id", Uuid, ForeignKey("warehouses.id"), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("status", Text, nullable=False),
    Column("reserved_at", DateTime(timezone=True), nullable=False),
    Column("closed_at", DateTime(timezone=True)),
)

fbo_shipments = Table(
    "fbo_shipments",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("product_id", Uuid, ForeignKey("products.id"), nullable=False),
    Column("warehouse_id", Uuid, ForeignKey("warehouses.id"), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("status", Text, nullable=False),
    Column("shipped_at", DateTime(timezone=True), nullable=False),
    Column("accepted_at", DateTime(timezone=True)),
)

movements = Table(
    "movements",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("seq", BigInteger, nullable=False),  # identity: порядок записей
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("operation", Text, nullable=False),
    Column("product_id", Uuid, ForeignKey("products.id"), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("from_kind", Text, nullable=False),
    Column("from_warehouse_id", Uuid, ForeignKey("warehouses.id")),
    Column("to_kind", Text, nullable=False),
    Column("to_warehouse_id", Uuid, ForeignKey("warehouses.id")),
    Column("document_id", Uuid),
)

idempotency_keys = Table(
    "idempotency_keys",
    metadata,
    Column("key", Text, primary_key=True),
    Column("fingerprint", Text, nullable=False),
    Column("result_id", Uuid),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
