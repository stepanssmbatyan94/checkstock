import type { ShortageDetails } from "@/shared/api/types";
import { Button } from "@/shared/ui";

import type { OperationKind } from "./OperationDialog";

interface Props {
  kind: OperationKind;
  shortage: ShortageDetails;
  warehouseName: string;
  onChooseWarehouse: (warehouseId: string) => void;
  onTransfer: (fromWarehouseId: string) => void;
}

/**
 * Нехватка на выбранном ФФ. Система сама ничего не делит между складами:
 * показывает, где товар есть, и предлагает менеджеру два понятных выхода.
 */
export default function ShortageNotice({
  kind,
  shortage,
  warehouseName,
  onChooseWarehouse,
  onTransfer,
}: Props) {
  const missing = shortage.requested - shortage.available;

  return (
    <div role="alert" className="mb-3 rounded-lg border border-accent/30 bg-accent-soft p-3 text-sm">
      <p className="font-medium text-accent">
        На ФФ «{warehouseName}» не хватает {missing} шт.
      </p>
      <p className="mt-1">
        Запрошено {shortage.requested}, доступно здесь {shortage.available}.{" "}
        {shortage.alternatives.length > 0
          ? `На других ФФ доступно ${shortage.available_elsewhere}:`
          : "На других действующих ФФ свободного товара нет."}
      </p>

      {shortage.alternatives.map((alternative) => {
        const coversAll = alternative.available >= shortage.requested;
        return (
          <div
            key={alternative.warehouse_id}
            className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-md bg-card px-3 py-2"
          >
            <span>
              {alternative.warehouse_name}: <b>{alternative.available}</b> шт.
            </span>
            <span className="flex gap-2">
              {coversAll && (
                <Button onClick={() => onChooseWarehouse(alternative.warehouse_id)}>
                  {kind === "transfer" ? "Отправить отсюда" : "Оформить здесь"}
                </Button>
              )}
              {kind !== "transfer" && (
                <Button onClick={() => onTransfer(alternative.warehouse_id)}>
                  Переместить на «{warehouseName}»
                </Button>
              )}
            </span>
          </div>
        );
      })}
    </div>
  );
}
