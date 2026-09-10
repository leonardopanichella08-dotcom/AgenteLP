import { useState, type ReactNode } from "react";
import clsx from "clsx";
import { CircleCheck, Copy, Loader2 } from "lucide-react";

/* ---------- atomi condivisi ---------- */

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
        {label}
      </span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-ink-faint">{hint}</span>}
    </label>
  );
}

export function Card({ title, right, children, className }: {
  title?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={clsx("rounded-2xl border border-line bg-surface p-5 shadow-card", className)}>
      {(title || right) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-sm font-semibold">{title}</h2>}
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function SkeletonBlock({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-line bg-surface px-5 py-6 text-[13px] text-ink-soft shadow-card">
      <Loader2 className="h-4 w-4 animate-spin text-brand" />
      {label}
    </div>
  );
}

export function Metric({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <span className="flex flex-col">
      <span className={clsx("text-[13px] font-semibold", strong ? "text-brand" : "text-ink")}>{value}</span>
      <span className="text-[10px] uppercase tracking-wide">{label}</span>
    </span>
  );
}

export function CopyButton({ text, label = "Copia" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1600);
        } catch {
          /* clipboard non disponibile */
        }
      }}
      className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium hover:border-line-strong"
    >
      {done ? <CircleCheck className="h-3.5 w-3.5 text-ok" /> : <Copy className="h-3.5 w-3.5" />}
      {done ? "Copiato" : label}
    </button>
  );
}

export function Pill({ children, tone = "muted" }: { children: ReactNode; tone?: "muted" | "ok" | "warn" | "brand" }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium",
        tone === "muted" && "bg-surface-sunken text-ink-soft",
        tone === "ok" && "border border-ok/30 bg-ok/5 text-ok",
        tone === "warn" && "border border-warn/30 bg-warn/5 text-warn",
        tone === "brand" && "border border-brand/30 bg-brand/5 text-brand",
      )}
    >
      {children}
    </span>
  );
}

/* ---------- helpers ---------- */

export function splitCsv(s: string): string[] {
  return s.split(",").map((x) => x.trim()).filter(Boolean);
}
export function joinTwo(a?: string | null, b?: string | null): string {
  return [a, b].filter(Boolean).join(" ");
}
export function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n).trimEnd()}…` : s;
}
export function fmt(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`;
  return String(n);
}
