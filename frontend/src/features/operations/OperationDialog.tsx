import { useRef, useState } from "react";

import { ApiError } from "@/shared/api/client";
import { useApiMutation, useProducts, useStock, useWarehouses } from "@/shared/api/hooks";
import type { ShortageDetails } from "@/shared/api/types";
import { Button, ErrorNote, Field, INPUT_CLASS, Modal } from "@/shared/ui";

import ShortageNotice from "./ShortageNotice";

export type OperationKind = "receipt" | "transfer" | "fbs" | "fbo";

export interface OperationDraft {
  kind: OperationKind;
  productId?: string;
  warehouseId?: string; // для перемещения — склад-источник
  toWarehouseId?: string;
  quantity?: number;
}

const CONFIG: Record<
  OperationKind,
  { title: string; submit: string; path: string; warehouseLabel: string }
> = {
  receipt: { title: "Приход товара", submit: "Оприходовать", path: "/receipts", warehouseLabel: "На какой ФФ" },
  transfer: { title: "Перемещение между ФФ", submit: "Отправить", path: "/transfers", warehouseLabel: "С какого ФФ" },
  fbs: { title: "Резерв под заказ FBS", submit: "Зарезервировать", path: "/fbs-orders", warehouseLabel: "На каком ФФ" },
  fbo: { title: "Отправка на склад маркетплейса (FBO)", submit: "Отправить", path: "/fbo-shipments", warehouseLabel: "С какого ФФ" },
};

interface Props {
  draft: OperationDraft;
  onClose: () => void;
  /** Нехватку можно закрыть перемещением: открыть его с подставленными полями. */
  onSwitch: (draft: OperationDraft) => void;
}

export default function OperationDialog({ draft, onClose, onSwitch }: Props) {
  const { kind } = draft;
  const config = CONFIG[kind];
  const products = useProducts().data ?? [];
  const warehouses = useWarehouses().data ?? [];
  const stock = useStock().data;
  const mutation = useApiMutation();

  const [productId, setProductId] = useState(draft.productId ?? "");
  const [warehouseId, setWarehouseId] = useState(draft.warehouseId ?? "");
  const [toWarehouseId, setToWarehouseId] = useState(draft.toWarehouseId ?? "");
  const [quantity, setQuantity] = useState(String(draft.quantity ?? ""));

  // Один и тот же набор полей отправляется с одним ключом идемпотентности:
  // двойной клик или повтор после обрыва сети не создаст второй документ.
  const attempt = useRef({ payload: "", key: "" });

  const active = warehouses.filter((w) => !w.is_archived);
  // Вывезти остатки можно и с удалённого ФФ, поэтому как источник
  // перемещения он остаётся в списке, пока на нём что-то лежит.
  const sources =
    kind === "transfer" ? warehouses.filter((w) => !w.is_archived || w.on_hand > 0) : active;

  const cell = stock?.rows
    .find((row) => row.product_id === productId)
    ?.cells.find((c) => c.warehouse_id === warehouseId);
  const showsAvailable = kind !== "receipt" && productId && warehouseId;

  const error = mutation.error instanceof ApiError ? mutation.error : null;
  const shortage =
    error?.code === "insufficient_stock" ? (error.details as unknown as ShortageDetails) : null;

  const amount = Number(quantity);
  const ready =
    productId && warehouseId && Number.isInteger(amount) && amount > 0 &&
    (kind !== "transfer" || toWarehouseId);

  function submit() {
    const body =
      kind === "transfer"
        ? { product_id: productId, from_warehouse_id: warehouseId, to_warehouse_id: toWarehouseId, quantity: amount }
        : { product_id: productId, warehouse_id: warehouseId, quantity: amount };
    const payload = JSON.stringify(body);
    if (attempt.current.payload !== payload) {
      attempt.current = { payload, key: crypto.randomUUID() };
    }
    mutation.mutate(
      { path: config.path, body, idempotencyKey: attempt.current.key },
      { onSuccess: onClose },
    );
  }

  function chooseWarehouse(id: string) {
    setWarehouseId(id);
    mutation.reset();
  }

  return (
    <Modal title={config.title} onClose={onClose}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (ready) submit();
        }}
      >
        <Field label="Товар">
          <select
            className={INPUT_CLASS}
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
          >
            <option value="">Выберите товар</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.sku} — {p.name}
              </option>
            ))}
          </select>
        </Field>

        <Field label={config.warehouseLabel}>
          <select
            className={INPUT_CLASS}
            value={warehouseId}
            onChange={(e) => setWarehouseId(e.target.value)}
          >
            <option value="">Выберите ФФ</option>
            {sources.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
                {w.is_archived ? " (удалён)" : ""}
              </option>
            ))}
          </select>
          {showsAvailable && (
            <span className="mt-1 block text-xs text-muted">
              Доступно здесь: <b className="text-ink">{cell?.available ?? 0}</b> шт.
              {cell && cell.reserved > 0 && ` (ещё ${cell.reserved} в резерве FBS)`}
            </span>
          )}
        </Field>

        {kind === "transfer" && (
          <Field label="На какой ФФ">
            <select
              className={INPUT_CLASS}
              value={toWarehouseId}
              onChange={(e) => setToWarehouseId(e.target.value)}
            >
              <option value="">Выберите ФФ</option>
              {active
                .filter((w) => w.id !== warehouseId)
                .map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
            </select>
          </Field>
        )}

        <Field label="Количество, шт.">
          <input
            className={INPUT_CLASS}
            type="number"
            min={1}
            step={1}
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
        </Field>

        {shortage ? (
          <ShortageNotice
            kind={kind}
            shortage={shortage}
            warehouseName={warehouses.find((w) => w.id === warehouseId)?.name ?? ""}
            onChooseWarehouse={chooseWarehouse}
            onTransfer={(fromWarehouseId) =>
              onSwitch({
                kind: "transfer",
                productId,
                warehouseId: fromWarehouseId,
                toWarehouseId: warehouseId,
                quantity: shortage.requested - shortage.available,
              })
            }
          />
        ) : (
          error && <ErrorNote>{error.message}</ErrorNote>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <Button onClick={onClose}>Отмена</Button>
          <Button type="submit" variant="primary" disabled={!ready || mutation.isPending}>
            {mutation.isPending ? "Отправляем…" : config.submit}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
