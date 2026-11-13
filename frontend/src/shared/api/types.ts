// Типы ответов API. Повторяют app/api/schemas.py на бэкенде.

export interface Warehouse {
  id: string;
  name: string;
  is_archived: boolean;
  deleted_at: string | null;
  on_hand: number;
  reserved: number;
  incoming: number;
}

export interface Product {
  id: string;
  sku: string;
  name: string;
}

export interface StockCell {
  warehouse_id: string;
  on_hand: number;
  reserved: number;
  available: number;
}

export interface StockRow {
  product_id: string;
  sku: string;
  name: string;
  cells: StockCell[];
  total_on_hand: number;
  total_reserved: number;
  total_available: number;
  in_transit_transfer: number;
  in_transit_fbo: number;
  in_transit_fbs: number;
  at_marketplace: number;
}

export interface StockOverview {
  shop_name: string;
  warehouses: Warehouse[];
  rows: StockRow[];
}

export interface Transfer {
  id: string;
  sku: string;
  product_name: string;
  from_warehouse: string;
  to_warehouse: string;
  quantity: number;
  status: "shipped" | "received";
  shipped_at: string;
  received_at: string | null;
}

export interface FbsOrder {
  id: string;
  sku: string;
  product_name: string;
  warehouse: string;
  quantity: number;
  status: "reserved" | "shipped" | "cancelled";
  reserved_at: string;
  closed_at: string | null;
}

export interface FboShipment {
  id: string;
  sku: string;
  product_name: string;
  warehouse: string;
  quantity: number;
  status: "in_transit" | "accepted";
  shipped_at: string;
  accepted_at: string | null;
}

export interface Movement {
  id: string;
  created_at: string;
  operation: string;
  sku: string;
  product_name: string;
  quantity: number;
  from_kind: string;
  from_warehouse: string | null;
  to_kind: string;
  to_warehouse: string | null;
}

export interface Reconciliation {
  consistent: boolean;
  discrepancies: unknown[];
}

export interface StockAlternative {
  warehouse_id: string;
  warehouse_name: string;
  available: number;
}

export interface ShortageDetails {
  requested: number;
  available: number;
  available_elsewhere: number;
  alternatives: StockAlternative[];
}
