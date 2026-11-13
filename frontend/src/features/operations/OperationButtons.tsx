import { useState } from "react";

import { Button } from "@/shared/ui";

import OperationDialog, { type OperationDraft, type OperationKind } from "./OperationDialog";

const BUTTONS: { kind: OperationKind; label: string }[] = [
  { kind: "receipt", label: "+ Приход" },
  { kind: "transfer", label: "Перемещение" },
  { kind: "fbs", label: "Резерв FBS" },
  { kind: "fbo", label: "Отправка FBO" },
];

export default function OperationButtons() {
  const [draft, setDraft] = useState<OperationDraft | null>(null);

  return (
    <>
      <div className="flex flex-wrap gap-2">
        {BUTTONS.map(({ kind, label }) => (
          <Button
            key={kind}
            variant={kind === "receipt" ? "primary" : "secondary"}
            onClick={() => setDraft({ kind })}
          >
            {label}
          </Button>
        ))}
      </div>
      {draft && (
        // key пересоздаёт диалог при переключении на другую операцию,
        // чтобы поля взяли значения из нового черновика.
        <OperationDialog
          key={`${draft.kind}:${draft.warehouseId ?? ""}`}
          draft={draft}
          onClose={() => setDraft(null)}
          onSwitch={setDraft}
        />
      )}
    </>
  );
}
