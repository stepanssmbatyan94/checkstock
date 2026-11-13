// Перевод кодов бэкенда в слова, понятные менеджеру.

export const OPERATION_LABELS: Record<string, string> = {
  receipt: "Приход",
  transfer_shipped: "Перемещение отправлено",
  transfer_received: "Перемещение принято",
  fbs_reserved: "Резерв FBS",
  fbs_cancelled: "Отмена резерва FBS",
  fbs_shipped: "Отправка FBS клиенту",
  fbo_shipped: "Отправка FBO",
  fbo_accepted: "Приёмка FBO на складе МП",
};

export const STATUS_LABELS: Record<string, string> = {
  shipped: "В пути",
  received: "Принято",
  reserved: "В резерве",
  cancelled: "Отменён",
  in_transit: "В пути",
  accepted: "Принято МП",
};

/** Счёт учёта → место, где числится товар. */
export function placeLabel(kind: string, warehouse: string | null): string {
  switch (kind) {
    case "supplier":
      return "Поставщик";
    case "warehouse_available":
      return `ФФ ${warehouse}`;
    case "warehouse_reserved":
      return `ФФ ${warehouse} · резерв FBS`;
    case "transit_transfer":
      return `В пути на ФФ ${warehouse}`;
    case "transit_fbo":
      return "В пути на склад МП (FBO)";
    case "marketplace":
      return "Склад маркетплейса";
    case "transit_fbs":
      return "В пути к клиенту (FBS)";
    default:
      return kind;
  }
}

const dateTime = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

export const formatDateTime = (iso: string) => dateTime.format(new Date(iso));
