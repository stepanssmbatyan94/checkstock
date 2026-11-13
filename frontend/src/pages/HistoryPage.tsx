import { useMovements } from "@/shared/api/hooks";
import { formatDateTime, OPERATION_LABELS, placeLabel } from "@/shared/lib/labels";
import { Card, EmptyRow, TD, TH } from "@/shared/ui";

export default function HistoryPage() {
  const movements = useMovements().data ?? [];

  return (
    <Card
      title="История операций"
      hint="Журнал движений: каждая строка — перенос товара из одного места в другое. Из него пересчитываются все остатки."
    >
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-line">
              {["Время", "Операция", "Товар", "Кол-во", "Откуда", "Куда"].map((title) => (
                <th key={title} className={TH}>
                  {title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {movements.length === 0 && <EmptyRow columns={6}>Операций пока нет</EmptyRow>}
            {movements.map((m) => (
              <tr key={m.id}>
                <td className={`${TD} num whitespace-nowrap text-muted`}>
                  {formatDateTime(m.created_at)}
                </td>
                <td className={TD}>{OPERATION_LABELS[m.operation] ?? m.operation}</td>
                <td className={TD}>
                  {m.sku} — {m.product_name}
                </td>
                <td className={`${TD} num font-medium`}>{m.quantity}</td>
                <td className={TD}>{placeLabel(m.from_kind, m.from_warehouse)}</td>
                <td className={TD}>{placeLabel(m.to_kind, m.to_warehouse)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
