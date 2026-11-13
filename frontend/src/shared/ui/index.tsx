import type { ButtonHTMLAttributes, ReactNode } from "react";
import { useEffect } from "react";

type ButtonVariant = "primary" | "secondary" | "danger";

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary: "bg-brand text-white hover:bg-brand/90",
  secondary: "bg-card text-ink border border-line hover:bg-brand-soft",
  danger: "bg-card text-accent border border-accent/40 hover:bg-accent-soft",
};

export function Button({
  variant = "secondary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      type="button"
      className={`rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${BUTTON_STYLES[variant]} ${className}`}
      {...props}
    />
  );
}

type BadgeTone = "neutral" | "good" | "warn" | "bad";

const BADGE_STYLES: Record<BadgeTone, string> = {
  neutral: "bg-line/60 text-muted",
  good: "bg-brand-soft text-brand",
  warn: "bg-warn-soft text-warn",
  bad: "bg-accent-soft text-accent",
};

export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: ReactNode }) {
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${BADGE_STYLES[tone]}`}
    >
      {children}
    </span>
  );
}

export function Card({ title, hint, children }: { title?: string; hint?: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-card">
      {title && (
        <header className="border-b border-line px-5 py-3">
          <h2 className="font-semibold">{title}</h2>
          {hint && <p className="mt-0.5 text-sm text-muted">{hint}</p>}
        </header>
      )}
      {children}
    </section>
  );
}

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-10 flex items-start justify-center overflow-y-auto bg-ink/40 p-4 pt-24"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <div role="dialog" aria-label={title} className="w-full max-w-md rounded-2xl bg-card p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-semibold">{title}</h2>
        {children}
      </div>
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="mb-3 block text-sm">
      <span className="mb-1 block text-muted">{label}</span>
      {children}
    </label>
  );
}

export const INPUT_CLASS =
  "w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-brand";

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="mb-3 rounded-lg bg-accent-soft px-3 py-2 text-sm text-accent">
      {children}
    </p>
  );
}

export function EmptyRow({ columns, children }: { columns: number; children: ReactNode }) {
  return (
    <tr>
      <td colSpan={columns} className="px-5 py-6 text-center text-sm text-muted">
        {children}
      </td>
    </tr>
  );
}

export const TH = "px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-muted";
export const TD = "px-4 py-2.5 text-sm";
