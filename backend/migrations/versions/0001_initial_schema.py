"""Начальная схема CheckStock.

Миграция написана на чистом SQL намеренно: ограничения, на которых держится
учёт, должны читаться глазами, а не выводиться из ORM-моделей.

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


UPGRADE_STATEMENTS = (
    """
    CREATE TABLE shops (
        id   uuid PRIMARY KEY,
        name text NOT NULL
    )
    """,
    """
    CREATE TABLE products (
        id      uuid PRIMARY KEY,
        shop_id uuid NOT NULL REFERENCES shops (id),
        sku     text NOT NULL UNIQUE,
        name    text NOT NULL
    )
    """,
    """
    CREATE TABLE warehouses (
        id         uuid PRIMARY KEY,
        name       text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        -- Удаление ФФ мягкое: строка остаётся, чтобы остатки и история
        -- продолжали на неё ссылаться.
        deleted_at timestamptz
    )
    """,
    """
    -- Имя уникально только среди действующих ФФ: после удаления «Юг»
    -- можно завести новый склад с тем же названием.
    CREATE UNIQUE INDEX uq_warehouses_active_name
        ON warehouses (lower(name))
        WHERE deleted_at IS NULL
    """,
    """
    CREATE TABLE stock (
        product_id   uuid NOT NULL REFERENCES products (id),
        warehouse_id uuid NOT NULL REFERENCES warehouses (id),
        on_hand      integer NOT NULL DEFAULT 0,
        reserved     integer NOT NULL DEFAULT 0,
        PRIMARY KEY (product_id, warehouse_id),
        -- Последний рубеж: даже при ошибке в коде остаток не уйдёт
        -- в минус и резерв не превысит физическое количество.
        CONSTRAINT ck_stock_on_hand_non_negative CHECK (on_hand >= 0),
        CONSTRAINT ck_stock_reserved_non_negative CHECK (reserved >= 0),
        CONSTRAINT ck_stock_reserved_within_on_hand CHECK (reserved <= on_hand)
    )
    """,
    """
    CREATE TABLE transfers (
        id                uuid PRIMARY KEY,
        product_id        uuid NOT NULL REFERENCES products (id),
        from_warehouse_id uuid NOT NULL REFERENCES warehouses (id),
        to_warehouse_id   uuid NOT NULL REFERENCES warehouses (id),
        quantity          integer NOT NULL CHECK (quantity > 0),
        status            text NOT NULL CHECK (status IN ('shipped', 'received')),
        shipped_at        timestamptz NOT NULL,
        received_at       timestamptz,
        CONSTRAINT ck_transfers_different_warehouses
            CHECK (from_warehouse_id <> to_warehouse_id)
    )
    """,
    """
    CREATE TABLE fbs_orders (
        id           uuid PRIMARY KEY,
        product_id   uuid NOT NULL REFERENCES products (id),
        warehouse_id uuid NOT NULL REFERENCES warehouses (id),
        quantity     integer NOT NULL CHECK (quantity > 0),
        status       text NOT NULL
            CHECK (status IN ('reserved', 'shipped', 'cancelled')),
        reserved_at  timestamptz NOT NULL,
        closed_at    timestamptz
    )
    """,
    """
    CREATE TABLE fbo_shipments (
        id           uuid PRIMARY KEY,
        product_id   uuid NOT NULL REFERENCES products (id),
        warehouse_id uuid NOT NULL REFERENCES warehouses (id),
        quantity     integer NOT NULL CHECK (quantity > 0),
        status       text NOT NULL CHECK (status IN ('in_transit', 'accepted')),
        shipped_at   timestamptz NOT NULL,
        accepted_at  timestamptz
    )
    """,
    """
    -- Журнал движений: только добавление строк. Каждая строка —
    -- перенос количества со счёта (from_*) на счёт (to_*).
    CREATE TABLE movements (
        id                uuid PRIMARY KEY,
        seq               bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
        created_at        timestamptz NOT NULL DEFAULT clock_timestamp(),
        operation         text NOT NULL,
        product_id        uuid NOT NULL REFERENCES products (id),
        quantity          integer NOT NULL CHECK (quantity > 0),
        from_kind         text NOT NULL,
        from_warehouse_id uuid REFERENCES warehouses (id),
        to_kind           text NOT NULL,
        to_warehouse_id   uuid REFERENCES warehouses (id),
        document_id       uuid
    )
    """,
    """
    CREATE INDEX ix_movements_product ON movements (product_id)
    """,
    """
    CREATE TABLE idempotency_keys (
        key         text PRIMARY KEY,
        fingerprint text NOT NULL,
        result_id   uuid,
        created_at  timestamptz NOT NULL DEFAULT now()
    )
    """,
)


def upgrade() -> None:
    # asyncpg выполняет по одной команде за запрос, поэтому не одним блоком.
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE idempotency_keys, movements, fbo_shipments, fbs_orders,
                   transfers, stock, warehouses, products, shops;
        """
    )
