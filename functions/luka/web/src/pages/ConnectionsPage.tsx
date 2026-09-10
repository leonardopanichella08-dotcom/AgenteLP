import { useMutation, useQuery } from "@tanstack/react-query";
import { Building2, FileText, Loader2, Plus, RefreshCw, Trash2, User } from "lucide-react";
import { api } from "../api";
import { useApp } from "../state";
import { Card, Pill, SkeletonBlock, joinTwo } from "../ui";
import type { Connection } from "../types";

export default function ConnectionsPage() {
  const { connections, loading, active, setActiveId, openAdd, refreshConnections } = useApp();

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Profili Collegati</h1>
          <p className="text-[13px] text-ink-soft">
            Profili e Pagine LinkedIn su cui lavora l'agente. Puoi collegarne più di uno.
          </p>
        </div>
        <button
          onClick={openAdd}
          className="inline-flex items-center gap-1.5 rounded-lg bg-brand px-4 py-2 text-[13px] font-semibold text-white hover:bg-brand-hover"
        >
          <Plus className="h-4 w-4" /> Collega profilo
        </button>
      </div>

      {loading && <SkeletonBlock label="Carico i profili…" />}
      {!loading && connections.length === 0 && (
        <Card>
          <p className="py-8 text-center text-[13px] text-ink-soft">
            Nessun profilo. Clicca <b>Collega profilo</b> per iniziare.
          </p>
        </Card>
      )}

      <div className="space-y-3">
        {connections.map((c) => (
          <ConnectionCard
            key={c.id}
            conn={c}
            isActive={c.id === active?.id}
            onSelect={() => setActiveId(c.id)}
            onChanged={refreshConnections}
          />
        ))}
      </div>
    </div>
  );
}

function ConnectionCard({
  conn,
  isActive,
  onSelect,
  onChanged,
}: {
  conn: Connection;
  isActive: boolean;
  onSelect: () => void;
  onChanged: () => void;
}) {
  const docsQ = useQuery({ queryKey: ["docs", conn.id], queryFn: () => api.documents(conn.id) });
  const reanalyze = useMutation({ mutationFn: () => api.reanalyze(conn.id), onSuccess: onChanged });
  const del = useMutation({ mutationFn: () => api.deleteConnection(conn.id), onSuccess: onChanged });
  const delDoc = useMutation({
    mutationFn: (docId: string) => api.deleteDocument(conn.id, docId),
    onSuccess: () => docsQ.refetch(),
  });
  const bp = conn.brand_profile;
  const Icon = conn.account_type === "company" ? Building2 : User;

  return (
    <Card className={isActive ? "ring-1 ring-brand/40" : undefined}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-surface-sunken text-ink-soft">
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <p className="flex items-center gap-2 text-sm font-semibold">
              {conn.display_name}
              {isActive && <Pill tone="brand">attivo</Pill>}
            </p>
            <p className="text-[12px] text-ink-faint">{conn.headline || conn.industry || "—"}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!isActive && (
            <button
              onClick={onSelect}
              className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium hover:border-line-strong"
            >
              Rendi attivo
            </button>
          )}
          <button
            onClick={() => reanalyze.mutate()}
            disabled={reanalyze.isPending}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium hover:border-line-strong disabled:opacity-50"
          >
            {reanalyze.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Rianalizza
          </button>
          <button
            onClick={() => {
              if (confirm(`Scollegare "${conn.display_name}"? I dati generati per questo profilo verranno rimossi.`))
                del.mutate();
            }}
            disabled={del.isPending}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-warn hover:border-warn/40 disabled:opacity-50"
          >
            {del.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
            Scollega
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Field label="Mission & Value Prop" value={joinTwo(bp?.mission, bp?.value_proposition)} />
        <Field label="ICP & Market Context" value={joinTwo(bp?.icp, bp?.market_context)} />
      </div>
      {(bp?.niche || (bp?.keywords_primary?.length ?? 0) > 0) && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          {bp?.niche && <Pill tone="brand">{bp.niche}</Pill>}
          {[...(bp?.keywords_primary ?? []), ...(bp?.keywords_secondary ?? [])].slice(0, 12).map((k) => (
            <Pill key={k}>{k}</Pill>
          ))}
        </div>
      )}

      <div className="mt-4 border-t border-line pt-3">
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
          Documenti ({docsQ.data?.length ?? 0})
        </p>
        {docsQ.data && docsQ.data.length > 0 ? (
          <ul className="flex flex-wrap gap-2">
            {docsQ.data.map((d) => (
              <li
                key={d.id}
                className="inline-flex items-center gap-1.5 rounded-md bg-surface-sunken px-2 py-1 text-[11px] text-ink-soft"
              >
                <FileText className="h-3 w-3" /> {d.filename}
                <button
                  onClick={() => delDoc.mutate(d.id)}
                  className="ml-1 text-ink-faint hover:text-warn"
                  title="Rimuovi"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[12px] text-ink-faint">
            Nessun documento. Caricali dalla schermata dell'agente per dare più contesto a Luka.
          </p>
        )}
      </div>
    </Card>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface-muted p-3.5">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">{label}</p>
      <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">{value || "—"}</p>
    </div>
  );
}
