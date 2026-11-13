import { useState } from "react";

import { ApiError } from "@/shared/api/client";
import { useApiMutation, useWarehouses } from "@/shared/api/hooks";
import type { Warehouse } from "@/shared/api/types";
import { Badge, Button, Card, EmptyRow, ErrorNote, INPUT_CLASS, Modal, TD, TH } from "@/shared/ui";

function Holdings({ warehouse }: { warehouse: Warehouse }) {
  if (warehouse.on_hand === 0 && warehouse.incoming === 0) {
    return <span className="text-muted">пусто</span>;
  }
  return (
    <span className="num">
      {warehouse.on_hand} шт.
      {warehouse.reserved > 0 && `, из них ${warehouse.reserved} в резерве FBS`}
      {warehouse.incoming > 0 && ` · едет ещё ${warehouse.incoming}`}
    </span>
  );
}

export default function WarehousesPage() {
  const warehouses = useWarehouses().data ?? [];
  const mutation = useApiMutation();
  const [newName, setNewName] = useState("");
  const [editing, setEditing] = useState<{ id: string; name: string } | null>(null);
  const [deleting, setDeleting] = useState<Warehouse | null>(null);

  const active = warehouses.filter((w) => !w.is_archived);
  const archived = warehouses.filter((w) => w.is_archived);
  const error = mutation.error instanceof ApiError ? mutation.error.message : null;

  function create() {
    mutation.mutate(
      { path: "/warehouses", body: { name: newName } },
      { onSuccess: () => setNewName("") },
    );
  }

  function rename() {
    if (!editing) return;
    mutation.mutate(
      { path: `/warehouses/${editing.id}`, method: "PATCH", body: { name: editing.name } },
      { onSuccess: () => setEditing(null) },
    );
  }

  function remove() {
    if (!deleting) return;
    mutation.mutate(
      { path: `/warehouses/${deleting.id}`, method: "DELETE" },
      { onSettled: () => setDeleting(null) },
    );
  }

  return (
    <div className="space-y-5">
      {error && !deleting && <ErrorNote>{error}</ErrorNote>}

      <Card title="Действующие ФФ">
        <table className="w-full">
          <thead>
            <tr className="border-b border-line">
              <th className={TH}>Название</th>
              <th className={TH}>Числится на складе</th>
              <th />
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {active.length === 0 && <EmptyRow columns={3}>Нет действующих ФФ</EmptyRow>}
            {active.map((w) => (
              <tr key={w.id}>
                <td className={TD}>
                  {editing?.id === w.id ? (
                    <form
                      className="flex gap-2"
                      onSubmit={(event) => {
                        event.preventDefault();
                        rename();
                      }}
                    >
                      <input
                        autoFocus
                        aria-label="Новое название"
                        className={INPUT_CLASS}
                        value={editing.name}
                        onChange={(e) => setEditing({ id: w.id, name: e.target.value })}
                      />
                      <Button type="submit" variant="primary">Сохранить</Button>
                      <Button onClick={() => setEditing(null)}>Отмена</Button>
                    </form>
                  ) : (
                    <span className="font-medium">{w.name}</span>
                  )}
                </td>
                <td className={TD}><Holdings warehouse={w} /></td>
                <td className={`${TD} space-x-2 text-right`}>
                  {editing?.id !== w.id && (
                    <>
                      <Button onClick={() => { mutation.reset(); setEditing({ id: w.id, name: w.name }); }}>
                        Переименовать
                      </Button>
                      <Button variant="danger" onClick={() => { mutation.reset(); setDeleting(w); }}>
                        Удалить
                      </Button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <form
          className="flex gap-2 border-t border-line px-4 py-3"
          onSubmit={(event) => {
            event.preventDefault();
            create();
          }}
        >
          <input
            aria-label="Название нового ФФ"
            className={`${INPUT_CLASS} max-w-xs`}
            placeholder="Название нового ФФ"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <Button type="submit" variant="primary" disabled={!newName.trim() || mutation.isPending}>
            Добавить ФФ
          </Button>
        </form>
      </Card>

      {archived.length > 0 && (
        <Card
          title="Удалённые ФФ"
          hint="Остатки и история сохранены. Товар числится на удалённом складе, пока его не вывезут перемещением."
        >
          <table className="w-full">
            <tbody className="divide-y divide-line">
              {archived.map((w) => (
                <tr key={w.id}>
                  <td className={TD}>
                    <span className="font-medium">{w.name}</span> <Badge tone="bad">удалён</Badge>
                  </td>
                  <td className={TD}><Holdings warehouse={w} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {deleting && (
        <Modal title={`Удалить ФФ «${deleting.name}»?`} onClose={() => setDeleting(null)}>
          <div className="space-y-2 text-sm">
            <p>
              Сейчас на складе числится: <b><Holdings warehouse={deleting} /></b>
            </p>
            <p>
              Остатки и история не удаляются. Склад уйдёт в архив: новые приходы, резервы и
              отправки с него станут недоступны, но остаток можно будет вывезти перемещением, а уже
              оформленные заказы — завершить.
            </p>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button onClick={() => setDeleting(null)}>Отмена</Button>
            <Button variant="danger" disabled={mutation.isPending} onClick={remove}>
              Удалить ФФ
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
