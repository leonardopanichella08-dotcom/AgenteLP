import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bot, Clock, Link2, Sparkles, Wand2 } from "lucide-react";
import { api } from "../api";
import { useApp } from "../state";
import { Card, Pill, SkeletonBlock } from "../ui";

const AGENTS = [
  {
    key: "luka",
    name: "LUKA",
    desc: "Analisi LinkedIn, discovery post virali di nicchia, generazione commenti e repost.",
    status: "attivo" as const,
    to: "/",
    icon: Bot,
  },
  {
    key: "andrea",
    name: "ANDREA",
    desc: "Incubazione reversiva: distrugge una startup in 10 iterazioni, cervello di leggi di mercato, report + piano finanziario con formule vive.",
    status: "attivo" as const,
    to: "/andrea",
    icon: Wand2,
  },
];

export default function DashboardPage() {
  const { connections, meta } = useApp();
  const tasksQ = useQuery({ queryKey: ["tasks"], queryFn: api.tasks });
  const tasks = tasksQ.data ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">AgenteLP</h1>
        <p className="text-[13px] text-ink-soft">Il tuo agente. Ogni funzione è un agente specializzato.</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Funzioni attive" value="2" sub="LUKA · ANDREA" />
        <Stat label="Profili collegati" value={String(connections.length)} sub="LinkedIn" />
        <Stat
          label="Motore"
          value={meta?.generation_mode === "llm" ? (meta?.model ?? "AI") : "demo"}
          sub={`discovery: ${meta?.discovery_provider ?? "—"}`}
        />
      </div>

      <Card title="Funzioni">
        <div className="grid gap-3 sm:grid-cols-2">
          {AGENTS.map((a) => {
            const inner = (
              <div
                className={`flex h-full flex-col rounded-xl border p-4 transition ${
                  a.to ? "border-line bg-surface hover:border-brand/40 hover:shadow-card" : "border-dashed border-line bg-surface-muted"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div
                      className={`grid h-9 w-9 place-items-center rounded-lg ${
                        a.status === "attivo" ? "bg-brand text-white" : "bg-surface-sunken text-ink-faint"
                      }`}
                    >
                      <a.icon className="h-4 w-4" />
                    </div>
                    <span className="text-sm font-semibold">{a.name}</span>
                  </div>
                  <Pill tone={a.status === "attivo" ? "ok" : "muted"}>{a.status}</Pill>
                </div>
                <p className="mt-2 text-[13px] leading-relaxed text-ink-soft">{a.desc}</p>
                {a.to && (
                  <span className="mt-3 inline-flex items-center gap-1 text-[12px] font-medium text-brand">
                    <Sparkles className="h-3.5 w-3.5" /> Apri
                  </span>
                )}
              </div>
            );
            return a.to ? (
              <Link key={a.key} to={a.to}>{inner}</Link>
            ) : (
              <div key={a.key}>{inner}</div>
            );
          })}
        </div>
      </Card>

      <Card title="Attività recente">
        {tasksQ.isLoading && <SkeletonBlock label="Carico l'attività…" />}
        {!tasksQ.isLoading && tasks.length === 0 && (
          <p className="py-6 text-center text-[13px] text-ink-soft">
            Nessuna attività. Vai su <Link className="font-medium text-brand" to="/">Agente Luka</Link> e avvia una ricerca.
          </p>
        )}
        <ul className="divide-y divide-line">
          {tasks.slice(0, 12).map((t) => {
            const s = t.result_summary ?? {};
            return (
              <li key={t.id} className="flex items-center justify-between gap-3 py-2.5 text-[13px]">
                <div className="flex min-w-0 items-center gap-2.5">
                  <Clock className="h-3.5 w-3.5 shrink-0 text-ink-faint" />
                  <span className="truncate">
                    <b className="font-medium capitalize">{t.type.replace("_", " ")}</b>
                    {s.discovered != null && ` · ${s.discovered} post`}
                    {s.comments_generated != null && ` · ${s.comments_generated} risposte`}
                    {s.provider ? ` · ${s.provider}` : ""}
                  </span>
                </div>
                <span className="flex shrink-0 items-center gap-2 text-[11px] text-ink-faint">
                  {fmtDate(t.finished_at ?? t.queued_at)}
                  <Pill tone={t.status === "succeeded" ? "ok" : t.status === "failed" ? "warn" : "muted"}>
                    {t.status}
                  </Pill>
                </span>
              </li>
            );
          })}
        </ul>
      </Card>

      {connections.length === 0 && (
        <Card>
          <div className="flex items-center gap-3 text-[13px]">
            <Link2 className="h-4 w-4 text-brand" />
            Nessun profilo collegato. Aprilo da <Link className="font-medium text-brand" to="/connections">Profili Collegati</Link>.
          </div>
        </Card>
      )}
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-card">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">{label}</p>
      <p className="mt-1 truncate text-lg font-semibold">{value}</p>
      {sub && <p className="text-[11px] text-ink-faint">{sub}</p>}
    </div>
  );
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("it", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}
