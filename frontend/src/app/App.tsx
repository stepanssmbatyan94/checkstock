import { NavLink, Route, Routes } from "react-router-dom";

import HistoryPage from "@/pages/HistoryPage";
import ShipmentsPage from "@/pages/ShipmentsPage";
import StockPage from "@/pages/StockPage";
import WarehousesPage from "@/pages/WarehousesPage";
import { useReconciliation, useStock } from "@/shared/api/hooks";
import { Badge } from "@/shared/ui";

const NAV = [
  { to: "/", label: "Остатки" },
  { to: "/shipments", label: "Отправки и перемещения" },
  { to: "/warehouses", label: "Склады ФФ" },
  { to: "/history", label: "История" },
];

export default function App() {
  const shopName = useStock().data?.shop_name;
  const reconciliation = useReconciliation().data;

  return (
    <div className="mx-auto max-w-7xl px-6 py-6">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-brand">
            CheckStock{shopName && ` · ${shopName}`}
          </p>
          <h1 className="text-2xl font-semibold">Где сейчас товар?</h1>
        </div>
        {reconciliation && (
          <span title="Остатки пересчитаны из журнала движений и сверены с таблицей остатков и документами в пути">
            {reconciliation.consistent ? (
              <Badge tone="good">✓ Учёт сходится с журналом</Badge>
            ) : (
              <Badge tone="bad">
                ✕ Расхождение с журналом: {reconciliation.discrepancies.length}
              </Badge>
            )}
          </span>
        )}
      </header>

      <nav className="mb-6 flex flex-wrap gap-1 border-b border-line">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end
            className={({ isActive }) =>
              `-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
                isActive
                  ? "border-brand text-brand"
                  : "border-transparent text-muted hover:text-ink"
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <Routes>
        <Route path="/" element={<StockPage />} />
        <Route path="/shipments" element={<ShipmentsPage />} />
        <Route path="/warehouses" element={<WarehousesPage />} />
        <Route path="/history" element={<HistoryPage />} />
      </Routes>
    </div>
  );
}
