import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type {
  FboShipment,
  FbsOrder,
  Movement,
  Product,
  Reconciliation,
  StockOverview,
  Transfer,
  Warehouse,
} from "./types";

const useGet = <T>(key: string, path: string) =>
  useQuery({ queryKey: [key], queryFn: () => api<T>(path) });

export const useStock = () => useGet<StockOverview>("stock", "/stock");
export const useReconciliation = () => useGet<Reconciliation>("reconciliation", "/reconciliation");
export const useProducts = () => useGet<Product[]>("products", "/products");
export const useWarehouses = () => useGet<Warehouse[]>("warehouses", "/warehouses");
export const useTransfers = () => useGet<Transfer[]>("transfers", "/transfers");
export const useFbsOrders = () => useGet<FbsOrder[]>("fbs-orders", "/fbs-orders");
export const useFboShipments = () => useGet<FboShipment[]>("fbo-shipments", "/fbo-shipments");
export const useMovements = () => useGet<Movement[]>("movements", "/movements");

export interface ApiCall {
  path: string;
  method?: "POST" | "PATCH" | "DELETE";
  body?: unknown;
  idempotencyKey?: string;
}

/**
 * Любое изменение учёта затрагивает сразу несколько экранов (остатки,
 * документы, историю, сверку), поэтому после него перечитываем всё.
 * На объёме прототипа это дешевле и надёжнее точечной инвалидации.
 */
export function useApiMutation<T = unknown>() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (call: ApiCall) =>
      api<T>(call.path, { ...call, method: call.method ?? "POST" }),
    onSettled: () => queryClient.invalidateQueries(),
  });
}
