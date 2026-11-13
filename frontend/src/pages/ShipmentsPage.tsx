import type { ReactNode } from "react";

import OperationButtons from "@/features/operations/OperationButtons";
import { ApiError } from "@/shared/api/client";
import {
  useApiMutation,
  useFboShipments,
  useFbsOrders,
  useTransfers,
} from "@/shared/api/hooks";
import { formatDateTime, STATUS_LABELS } from "@/shared/lib/labels";
import { Badge, Button, Card, EmptyRow, ErrorNote, TD, TH } from "@/shared/ui";

const TONE: Record<string, "warn" | "good" | "neutral"> = {
  shipped: "warn",
  in_transit: "warn",
  reserved: "warn",
  received: "good",
  accepted: "good",
  cancelled: "neutral",
};

function Status({ status, label }: { status: string; label?: string }) {
  return <Badge tone={TONE[status]}>{label ?? STATUS_LABELS[status]}</Badge>;
}

function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-line">
            {head.map((title) => (
              <th key={title} className={TH}>
                {title}
              </th>
            ))}
            <th />
          </tr>
        </thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  );
}

export default function ShipmentsPage() {
  const transfers = useTransfers().data ?? [];
  const fbsOrders = useFbsOrders().data ?? [];
  const fboShipments = useFboShipments().data ?? [];
  const mutation = useApiMutation();
  const confirm = (path: string) => mutation.mutate({ path });
  const busy = mutation.isPending;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">
          Подтверждение можно нажать повторно — товар не спишется и не придёт дважды.
        </p>
        <OperationButtons />
      </div>

      {mutation.error instanceof ApiError && <ErrorNote>{mutation.error.message}</ErrorNote>}

      <Card title="Перемещения между ФФ" hint="Отправленный товар числится в пути, пока его не примут на складе назначения.">
        <Table head={["Отправлено", "Товар", "Кол-во", "Откуда", "Куда", "Статус"]}>
          {transfers.length === 0 && <EmptyRow columns={7}>Перемещений пока нет</EmptyRow>}
          {transfers.map((t) => (
            <tr key={t.id}>
              <td className={TD}>{formatDateTime(t.shipped_at)}</td>
              <td className={TD}>{t.sku} — {t.product_name}</td>
              <td className={`${TD} num`}>{t.quantity}</td>
              <td className={TD}>{t.from_warehouse}</td>
              <td className={TD}>{t.to_warehouse}</td>
              <td className={TD}><Status status={t.status} /></td>
              <td className={`${TD} text-right`}>
                {t.status === "shipped" && (
                  <Button disabled={busy} onClick={() => confirm(`/transfers/${t.id}/receive`)}>
                    Принять на «{t.to_warehouse}»
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </Table>
      </Card>

      <Card title="Заказы FBS" hint="Резерв блокирует товар на ФФ до отправки клиенту или отмены.">
        <Table head={["Резерв", "Товар", "Кол-во", "ФФ", "Статус"]}>
          {fbsOrders.length === 0 && <EmptyRow columns={6}>Заказов FBS пока нет</EmptyRow>}
          {fbsOrders.map((o) => (
            <tr key={o.id}>
              <td className={TD}>{formatDateTime(o.reserved_at)}</td>
              <td className={TD}>{o.sku} — {o.product_name}</td>
              <td className={`${TD} num`}>{o.quantity}</td>
              <td className={TD}>{o.warehouse}</td>
              <td className={TD}>
                <Status status={o.status} label={o.status === "shipped" ? "Едет к клиенту" : undefined} />
              </td>
              <td className={`${TD} space-x-2 text-right`}>
                {o.status === "reserved" && (
                  <>
                    <Button disabled={busy} onClick={() => confirm(`/fbs-orders/${o.id}/ship`)}>
                      Отправить клиенту
                    </Button>
                    <Button variant="danger" disabled={busy} onClick={() => confirm(`/fbs-orders/${o.id}/cancel`)}>
                      Отменить
                    </Button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </Table>
      </Card>

      <Card title="Поставки FBO" hint="Товар покинул ФФ и числится в пути, пока его не примет склад маркетплейса.">
        <Table head={["Отправлено", "Товар", "Кол-во", "С какого ФФ", "Статус"]}>
          {fboShipments.length === 0 && <EmptyRow columns={6}>Поставок FBO пока нет</EmptyRow>}
          {fboShipments.map((f) => (
            <tr key={f.id}>
              <td className={TD}>{formatDateTime(f.shipped_at)}</td>
              <td className={TD}>{f.sku} — {f.product_name}</td>
              <td className={`${TD} num`}>{f.quantity}</td>
              <td className={TD}>{f.warehouse}</td>
              <td className={TD}><Status status={f.status} /></td>
              <td className={`${TD} text-right`}>
                {f.status === "in_transit" && (
                  <Button disabled={busy} onClick={() => confirm(`/fbo-shipments/${f.id}/accept`)}>
                    Принято складом МП
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </Table>
      </Card>
    </div>
  );
}
