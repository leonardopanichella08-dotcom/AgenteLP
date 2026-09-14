import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import {
  AlertTriangle,
  ChevronDown,
  Download,
  FileSpreadsheet,
  FileText,
  Loader2,
  Skull,
  Sparkles,
  Trash2,
} from "lucide-react";
import { api } from "../api";
import { Card, Pill } from "../ui";
import type { AndreaRun } from "../types";

const PROB_TONE: Record<string, "warn" | "muted"> = {
  CERTA: "warn",
  ALTA: "warn",
  "MEDIA-ALTA": "warn",
};

export default function AndreaPage() {
  const qc = useQueryClient();
  const runsQ = useQuery({ queryKey: ["andrea-runs"], queryFn: api.andreaRuns });
  const lawsQ = useQuery({ queryKey: ["andrea-laws"], queryFn: api.andreaLaws });
  const [runId, setRunId] = useState<string | null>(null);

  const runQ = useQuery({
    queryKey: ["andrea-run", runId],
    queryFn: () => api.andreaRun(runId!),
    enabled: !!runId,
  });
  const run = runId ? runQ.data : null;

  const create = useMutation({
    mutationFn: api.andreaCreate,
    onSuccess: (r) => {
      setRunId(r.id);
      qc.setQueryData(["andrea-run", r.id], r);
      qc.invalidateQueries({ queryKey: ["andrea-runs"] });
    },
  });

  // loop automatico degli step finche' il run e' "running"
  const stepping = useRef(false);
  const [stepError, setStepError] = useState<string | null>(null);
  useEffect(() => {
    if (!run || run.status !== "running" || stepping.current) return;
    stepping.current = true;
    setStepError(null);
    api
      .andreaStep(run.id)
      .then((r) => {
        qc.setQueryData(["andrea-run", r.id], r);
        if (r.status !== "running") qc.invalidateQueries({ queryKey: ["andrea-laws"] });
      })
      .catch((e: Error) => setStepError(e.message))
      .finally(() => {
        stepping.current = false;
        setTimeout(() => qc.invalidateQueries({ queryKey: ["andrea-run", run.id] }), 300);
      });
    // le due sotto-fasi finali (report -> dossier) non incrementano
    // current_iteration: senza questi due flag il loop si fermerebbe dopo il
    // report e non proseguirebbe da solo alla scrittura del dossier.
  }, [run?.id, run?.status, run?.current_iteration, !!run?.final_report, !!run?.dossier, qc]); // eslint-disable-line

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_260px]">
      <div className="min-w-0 space-y-6">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">ANDREA — A.I.R.S.</h1>
          <p className="text-[13px] text-ink-soft">
            Incubazione reversiva: distrugge l'idea in 10 iterazioni (stress-test sistemico →
            casi reali → ridisegno), poi report + piano finanziario con formule vive + dossier
            narrativo completo (8-9 pagine) come descrizione definitiva del progetto.
          </p>
        </div>

        {!runId && (
          <NewRunForm
            onSubmit={(v) => create.mutate(v)}
            pending={create.isPending}
            error={create.error ? (create.error as Error).message : null}
          />
        )}

        {run && (
          <RunView
            run={run}
            stepError={stepError}
            onReset={() => setRunId(null)}
          />
        )}
      </div>

      {/* sidebar: run passati + cervello */}
      <div className="space-y-4">
        <Card title="Cervello">
          <p className="text-[13px]">
            <b className="text-lg font-semibold">{lawsQ.data?.length ?? "…"}</b>{" "}
            <span className="text-ink-soft">leggi di mercato accumulate</span>
          </p>
          <p className="mt-1 text-[11px] text-ink-faint">Crescono a ogni analisi completata.</p>
        </Card>
        <Card title="Analisi precedenti">
          {runsQ.data && runsQ.data.length > 0 ? (
            <ul className="space-y-1.5">
              {runsQ.data.map((r) => (
                <li key={r.id}>
                  <button
                    onClick={() => setRunId(r.id)}
                    className={clsx(
                      "flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left text-[12px] hover:bg-surface-muted",
                      r.id === runId && "bg-surface-sunken",
                    )}
                  >
                    <span className="truncate">{r.startup_name}</span>
                    <Pill tone={r.status === "succeeded" ? "ok" : r.status === "failed" ? "warn" : "muted"}>
                      {r.status === "running" ? `${r.current_iteration}/${r.max_iterations}` : r.status}
                    </Pill>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[12px] text-ink-faint">Nessuna analisi ancora.</p>
          )}
          {runId && (
            <button
              onClick={() => setRunId(null)}
              className="mt-2 text-[11px] font-medium text-brand hover:underline"
            >
              + Nuova analisi
            </button>
          )}
        </Card>
      </div>
    </div>
  );
}

function NewRunForm({
  onSubmit,
  pending,
  error,
}: {
  onSubmit: (v: { startup_name: string; input_text: string; max_iterations: number }) => void;
  pending: boolean;
  error: string | null;
}) {
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [iters, setIters] = useState(10);
  return (
    <Card title="Nuova startup da stressare">
      <div className="space-y-3">
        <input
          className="input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Nome della startup"
        />
        <textarea
          className="input min-h-[180px] resize-y"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Pitch, modello di business, numeri (ricavi, CAC, team, target). Più contesto dai, più l'analisi è precisa."
        />
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-[12px] text-ink-soft">
            Iterazioni distruttive
            <select
              className="input w-20"
              value={iters}
              onChange={(e) => setIters(Number(e.target.value))}
            >
              {[3, 5, 7, 10].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </label>
          <span className="text-[11px] text-ink-faint">~{Math.round((iters + 4) * 0.9)} min (incluso il dossier finale)</span>
        </div>
        {error && <p className="text-[12px] text-warn">{error}</p>}
        <button
          onClick={() => onSubmit({ startup_name: name.trim(), input_text: text.trim(), max_iterations: iters })}
          disabled={pending || name.trim().length < 2 || text.trim().length < 40}
          className="inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2.5 text-[13px] font-semibold text-white hover:bg-brand-hover disabled:opacity-50"
        >
          {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          Continua → allega documenti
        </button>
      </div>
    </Card>
  );
}

function RunView({ run, stepError, onReset }: { run: AndreaRun; stepError: string | null; onReset: () => void }) {
  const qc = useQueryClient();
  const del = useMutation({
    mutationFn: () => api.andreaDelete(run.id),
    onSuccess: onReset,
  });
  const start = useMutation({
    mutationFn: () => api.andreaStep(run.id),
    onSuccess: (r) => qc.setQueryData(["andrea-run", run.id], r),
  });
  const progress = run.status === "running"
    ? Math.round((run.current_iteration / run.max_iterations) * 100)
    : 100;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">{run.startup_name}</h2>
        <div className="flex items-center gap-2">
          <Pill tone={run.status === "succeeded" ? "ok" : run.status === "failed" ? "warn" : "brand"}>
            {run.status === "running"
              ? `iterazione ${run.current_iteration}/${run.max_iterations}`
              : run.status === "draft" ? "bozza" : run.status}
          </Pill>
          <button
            onClick={() => del.mutate()}
            className="rounded-md p-1 text-ink-faint hover:text-warn"
            title="Elimina analisi"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {run.status === "draft" && (
        <Card title="Materiale della startup">
          <p className="-mt-2 mb-3 whitespace-pre-line text-[13px] text-ink-soft">{run.input_text}</p>
          <DocPanel run={run} />
          {start.isError && (
            <p className="mt-3 text-[12px] text-warn">{(start.error as Error).message}</p>
          )}
          <button
            onClick={() => start.mutate()}
            disabled={start.isPending}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-brand-tech px-4 py-2.5 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {start.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Skull className="h-4 w-4" />}
            Avvia analisi distruttiva
          </button>
        </Card>
      )}

      {run.status === "running" && (
        <div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-sunken">
            <div className="h-full bg-brand transition-all" style={{ width: `${progress}%` }} />
          </div>
          <p className="mt-2 flex items-center gap-2 text-[12px] text-ink-soft">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-brand" />
            {run.current_iteration === 0
              ? "Costruisco la mappa sistemica e cerco le falle letali…"
              : run.current_iteration < run.max_iterations
              ? `Stress-test dell'iterazione ${run.current_iteration + 1}…`
              : !run.final_report
              ? "Scrivo il Report Strategico Definitivo…"
              : "Scrivo il Dossier di Progetto completo (8-9 pagine, può richiedere qualche minuto)…"}
          </p>
        </div>
      )}

      {stepError && (
        <p className="rounded-xl border border-warn/30 bg-warn/5 px-4 py-3 text-[13px] text-warn">
          Interruzione: {stepError}. L'analisi riprende da sola dall'ultimo punto salvato.
        </p>
      )}
      {run.status === "failed" && run.error && (
        <p className="rounded-xl border border-warn/30 bg-warn/5 px-4 py-3 text-[13px] text-warn">
          {run.error}
        </p>
      )}

      {/* falle letali */}
      {run.lethal_flaws.length > 0 && (
        <Card title="Le falle letali">
          <ul className="space-y-2">
            {run.lethal_flaws.map((f, i) => (
              <li key={i} className="flex items-start gap-2 text-[13px]">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
                <span>
                  <b>{f.flaw}</b>{" "}
                  <Pill tone={PROB_TONE[f.probability] ?? "muted"}>{f.probability}</Pill>
                  <span className="mt-0.5 block text-[12px] text-ink-soft">{f.death_mechanism}</span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* iterazioni */}
      {run.iterations.map((it) => (
        <Accordion
          key={it.index}
          title={`Iterazione ${it.index} — ${it.lethal_flaw}`}
          numbers={it.key_numbers}
        >
          <Md text={it.stress_test} />
          {it.research_notes && (
            <>
              <p className="mt-3 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
                Casi reali
              </p>
              <Md text={it.research_notes} />
            </>
          )}
          {it.version_md && (
            <>
              <p className="mt-3 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
                Versione V{it.index}
              </p>
              <Md text={it.version_md} />
            </>
          )}
        </Accordion>
      ))}

      {/* risultato finale */}
      {run.status === "succeeded" && (
        <>
          <Card
            title="Report Strategico V-FINALE"
            right={
              <div className="flex flex-wrap gap-2">
                <a
                  href={api.andreaArtifactUrl(run.id, "report_pdf")}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium hover:border-line-strong"
                >
                  <FileText className="h-3.5 w-3.5" /> Report PDF
                </a>
                <a
                  href={api.andreaArtifactUrl(run.id, "financial_xlsx")}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium hover:border-line-strong"
                >
                  <FileSpreadsheet className="h-3.5 w-3.5" /> Piano Finanziario XLSX
                </a>
                <a
                  href={api.andreaArtifactUrl(run.id, "narrative_pdf")}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium hover:border-line-strong"
                >
                  <Download className="h-3.5 w-3.5" /> Analisi Narrativa PDF
                </a>
              </div>
            }
          >
            <Md text={run.final_report} />
          </Card>

          <DossierCard run={run} />

          <details className="rounded-2xl border border-line bg-surface p-5 shadow-card">
            <summary className="cursor-pointer text-sm font-semibold">Analisi narrativa del piano</summary>
            <div className="mt-3">
              <Md text={run.narrative} />
            </div>
          </details>
          <details className="rounded-2xl border border-line bg-surface p-5 shadow-card">
            <summary className="cursor-pointer text-sm font-semibold">Mappa sistemica</summary>
            <div className="mt-3">
              <Md text={run.systemic_map} />
            </div>
          </details>
        </>
      )}
    </div>
  );
}

function DossierCard({ run }: { run: AndreaRun }) {
  const qc = useQueryClient();
  const gen = useMutation({
    mutationFn: () => api.andreaStep(run.id),
    onSuccess: (r) => qc.setQueryData(["andrea-run", run.id], r),
  });

  if (!run.dossier) {
    return (
      <Card title="Dossier di Progetto">
        <p className="text-[13px] text-ink-soft">
          Manca ancora il dossier narrativo completo (8-9 pagine): racconta il progetto dall'inizio
          alla versione finale e diventa la descrizione ufficiale della startup.
        </p>
        {gen.isError && (
          <p className="mt-2 text-[12px] text-warn">{(gen.error as Error).message}</p>
        )}
        <button
          onClick={() => gen.mutate()}
          disabled={gen.isPending}
          className="mt-3 inline-flex items-center gap-2 rounded-lg bg-brand-tech px-4 py-2.5 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-50"
        >
          {gen.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
          {gen.isPending ? "Scrivo il dossier (qualche minuto)…" : "Genera Dossier di Progetto"}
        </button>
      </Card>
    );
  }

  return (
    <details className="rounded-2xl border border-line bg-surface p-5 shadow-card" open>
      <summary className="flex cursor-pointer flex-wrap items-center justify-between gap-2 text-sm font-semibold">
        <span>Dossier di Progetto — descrizione completa</span>
        <a
          href={api.andreaArtifactUrl(run.id, "dossier_pdf")}
          onClick={(e) => e.stopPropagation()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium hover:border-line-strong"
        >
          <Download className="h-3.5 w-3.5" /> Dossier PDF
        </a>
      </summary>
      <div className="mt-3">
        <Md text={run.dossier} />
      </div>
    </details>
  );
}

function Accordion({
  title,
  numbers,
  children,
}: {
  title: string;
  numbers: Record<string, number>;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const nums = Object.entries(numbers || {}).filter(([, v]) => typeof v === "number");
  return (
    <div className="rounded-2xl border border-line bg-surface shadow-card">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-5 py-3.5 text-left"
      >
        <span className="text-[13px] font-semibold">{title}</span>
        <ChevronDown className={clsx("h-4 w-4 shrink-0 text-ink-faint transition", open && "rotate-180")} />
      </button>
      {nums.length > 0 && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 border-t border-line px-5 py-2 text-[11px] text-ink-faint">
          {nums.map(([k, v]) => (
            <span key={k}>
              <b className="text-ink-soft">{k.replace(/_/g, " ")}</b>: {fmtNum(v)}
            </span>
          ))}
        </div>
      )}
      {open && <div className="border-t border-line px-5 py-4 text-[13px] leading-relaxed">{children}</div>}
    </div>
  );
}

function fmtNum(v: number): string {
  if (Math.abs(v) >= 1000) return v.toLocaleString("it");
  return String(v);
}

function DocPanel({ run }: { run: AndreaRun }) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const upload = useMutation({
    mutationFn: (file: File) => api.andreaUploadDoc(run.id, file),
    onSuccess: (r) => qc.setQueryData(["andrea-run", run.id], r),
  });
  const del = useMutation({
    mutationFn: (docId: string) => api.andreaDeleteDoc(run.id, docId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["andrea-run", run.id] }),
  });

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        {run.documents.map((d) => (
          <span
            key={d.id}
            className="inline-flex items-center gap-1.5 rounded-md bg-surface-sunken px-2 py-1 text-[11px] text-ink-soft"
          >
            <FileText className="h-3 w-3" /> {d.filename}
            <button onClick={() => del.mutate(d.id)} className="ml-1 text-ink-faint hover:text-warn">
              ×
            </button>
          </span>
        ))}
        <button
          onClick={() => fileRef.current?.click()}
          disabled={upload.isPending}
          className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-line px-3 py-1.5 text-[12px] font-medium text-ink-soft hover:border-line-strong disabled:opacity-50"
        >
          {upload.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileText className="h-3.5 w-3.5" />}
          Allega PDF / Excel / Word
        </button>
        <input
          ref={fileRef}
          type="file"
          hidden
          accept=".pdf,.docx,.xlsx,.xlsm,.txt,.md,.csv"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upload.mutate(f);
            e.target.value = "";
          }}
        />
      </div>
      {upload.isError && (
        <p className="mt-1.5 text-[11px] text-warn">{(upload.error as Error).message}</p>
      )}
      <p className="mt-1.5 text-[11px] text-ink-faint">
        Pitch deck, piano finanziario, business plan… il testo viene estratto e aggiunto al
        contesto dell'analisi.
      </p>
    </div>
  );
}

/* mini renderer markdown */
function Md({ text }: { text: string }) {
  const lines = (text || "").split("\n");
  const out: React.ReactNode[] = [];
  let bullets: string[] = [];
  const flush = (key: number) => {
    if (bullets.length) {
      out.push(
        <ul key={`u${key}`} className="my-2 ml-4 list-disc space-y-1 text-ink-soft">
          {bullets.map((b, i) => <li key={i}>{clean(b)}</li>)}
        </ul>,
      );
      bullets = [];
    }
  };
  lines.forEach((raw, i) => {
    const l = raw.trim();
    if (!l) { flush(i); return; }
    if (l.startsWith("### ")) { flush(i); out.push(<p key={i} className="mt-3 text-[12px] font-semibold uppercase tracking-wide text-ink-faint">{clean(l.slice(4))}</p>); }
    else if (l.startsWith("## ")) { flush(i); out.push(<h4 key={i} className="mt-3 text-[13px] font-semibold text-ink">{clean(l.slice(3))}</h4>); }
    else if (l.startsWith("# ")) { flush(i); out.push(<h4 key={i} className="mt-3 text-sm font-semibold text-ink">{clean(l.slice(2))}</h4>); }
    else if (/^[-*]\s+/.test(l)) bullets.push(l.replace(/^[-*]\s+/, ""));
    else if (l.startsWith("|")) {
      const cells = l.split("|").map((c) => c.trim()).filter(Boolean);
      const isSep = /^[\s|:-]+$/.test(l);
      if (!isSep && cells.length) bullets.push(cells.join(" · "));
    }
    else { flush(i); out.push(<p key={i} className="my-1.5 text-ink-soft">{clean(l)}</p>); }
  });
  flush(9999);
  return <div className="text-[13px] leading-relaxed">{out}</div>;
}

function clean(s: string): string {
  return s.replace(/\*\*/g, "").replace(/`/g, "");
}
