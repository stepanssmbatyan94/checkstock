import OperationButtons from "@/features/operations/OperationButtons";
import { useStock } from "@/shared/api/hooks";
import { Badge, Card, EmptyRow } from "@/shared/ui";

const GROUP = "border-l border-line px-3 py-2 text-center text-xs font-semibold";
const SUB = "px-3 py-1.5 text-right text-xs font-medium text-muted";
const CELL = "num px-3 py-2.5 text-right text-sm";
const FIRST = "border-l border-line";

/** Ноль показываем приглушённо: глаз сразу находит, где товар есть. */
function Quantity({ value, tone = "text-ink" }: { value: number; tone?: string }) {
  return <span className={value === 0 ? "text-line" : tone}>{value}</span>;
}

export default function StockPage() {
  const { data, isLoading } = useStock();
  const warehouses = data?.warehouses ?? [];
  const rows = data?.rows ?? [];
  const columns = 2 + warehouses.length * 3 + 3 + 4;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">
          <b className="text-ink">Доступно</b> = физически на складе − резерв FBS. Товар в пути уже
          покинул ФФ и в остатки складов не входит.
        </p>
        <OperationButtons />
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-line">
                <th colSpan={2} />
                {warehouses.map((w) => (
                  <th key={w.id} colSpan={3} className={GROUP}>
                    ФФ {w.name} {w.is_archived && <Badge tone="bad">удалён</Badge>}
                  </th>
                ))}
                <th colSpan={3} className={`${GROUP} bg-brand-soft/60`}>
                  Всего на ФФ
                </th>
                <th colSpan={4} className={`${GROUP} bg-warn-soft/60`}>
                  Уже отправлено
                </th>
              </tr>
              <tr className="border-b border-line">
                <th className="px-4 py-1.5 text-left text-xs font-medium text-muted">Артикул</th>
                <th className="px-4 py-1.5 text-left text-xs font-medium text-muted">Товар</th>
                {warehouses.map((w) => (
                  <Subheads key={w.id} />
                ))}
                <Subheads className="bg-brand-soft/60" />
                <th className={`${SUB} ${FIRST} bg-warn-soft/60`}>Между ФФ</th>
                <th className={`${SUB} bg-warn-soft/60`}>FBO → склад МП</th>
                <th className={`${SUB} bg-warn-soft/60`}>FBS → клиент</th>
                <th className={`${SUB} bg-warn-soft/60`}>Принято МП</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <EmptyRow columns={columns}>{isLoading ? "Загрузка…" : "Товаров нет"}</EmptyRow>
              )}
              {rows.map((row) => (
                <tr key={row.product_id} className="border-b border-line last:border-0">
                  <td className="whitespace-nowrap px-4 py-2.5 text-sm font-medium">{row.sku}</td>
                  <td className="px-4 py-2.5 text-sm">{row.name}</td>
                  {row.cells.map((cell, index) => {
                    const archived = warehouses[index]?.is_archived;
                    return (
                      <Cells
                        key={cell.warehouse_id}
                        onHand={cell.on_hand}
                        // С удалённого ФФ продавать нельзя: товар числится, но не доступен.
                        available={archived ? 0 : cell.available}
                        reserved={cell.reserved}
                        className={archived ? "bg-accent-soft/40" : ""}
                      />
                    );
                  })}
                  <Cells
                    onHand={row.total_on_hand}
                    available={row.total_available}
                    reserved={row.total_reserved}
                    className="bg-brand-soft/60 font-semibold"
                  />
                  <td className={`${CELL} ${FIRST} bg-warn-soft/60`}>
                    <Quantity value={row.in_transit_transfer} />
                  </td>
                  <td className={`${CELL} bg-warn-soft/60`}>
                    <Quantity value={row.in_transit_fbo} />
                  </td>
                  <td className={`${CELL} bg-warn-soft/60`}>
                    <Quantity value={row.in_transit_fbs} />
                  </td>
                  <td className={`${CELL} bg-warn-soft/60`}>
                    <Quantity value={row.at_marketplace} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {warehouses.some((w) => w.is_archived) && (
        <p className="text-sm text-muted">
          Удалённый ФФ остаётся в таблице, пока на нём числится товар. Продавать с него нельзя —
          вывезите остаток перемещением на действующий ФФ.
        </p>
      )}
    </div>
  );
}

function Subheads({ className = "" }: { className?: string }) {
  return (
    <>
      <th className={`${SUB} ${FIRST} ${className}`}>Физически</th>
      <th className={`${SUB} ${className}`}>Доступно</th>
      <th className={`${SUB} ${className}`}>Резерв FBS</th>
    </>
  );
}

function Cells({
  onHand,
  available,
  reserved,
  className = "",
}: {
  onHand: number;
  available: number;
  reserved: number;
  className?: string;
}) {
  return (
    <>
      <td className={`${CELL} ${FIRST} ${className}`}>
        <Quantity value={onHand} />
      </td>
      <td className={`${CELL} ${className}`}>
        <Quantity value={available} tone="font-semibold text-brand" />
      </td>
      <td className={`${CELL} ${className}`}>
        <Quantity value={reserved} tone="text-warn" />
      </td>
    </>
  );
}
