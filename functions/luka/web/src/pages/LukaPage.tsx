import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import clsx from "clsx";
import {
  Bot,
  ChevronDown,
  ExternalLink,
  FileText,
  Globe2,
  Link2,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
} from "lucide-react";
import { api } from "../api";
import { useApp } from "../state";
import type { Connection, DiscoveredPost, Geo, TaskDetail } from "../types";
import { Card, CopyButton, Field, Metric, SkeletonBlock, fmt, joinTwo, splitCsv, truncate } from "../ui";

const DEFAULT_GEO: { value: Geo; label: string }[] = [
  { value: "world", label: "Mondo" },
  { value: "europe", label: "Europa" },
  { value: "italy", label: "Italia" },
];

const PROVIDER_LABEL: Record<string, string> = {
  free: "Hacker News (trend nicchia)",
  sample: "dataset locale",
  apify: "LinkedIn reale (Apify)",
};

export default function LukaPage() {
  const { meta, active, loading, refreshConnections, openAdd } = useApp();
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [params, setParams] = useSearchParams();

  useEffect(() => {
    setTask(null);
  }, [active?.id]);

  // ritorno dal callback OAuth LinkedIn
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    const li = params.get("linkedin");
    if (!li) return;
    setNotice(
      li === "connected"
        ? "Profilo LinkedIn collegato."
        : `Collegamento LinkedIn non riuscito (${params.get("reason") ?? "errore"}).`,
    );
    if (li === "connected") refreshConnections();
    params.delete("linkedin");
    params.delete("reason");
    params.delete("id");
    setParams(params, { replace: true });
    const t = setTimeout(() => setNotice(null), 4000);
    return () => clearTimeout(t);
  }, []); // eslint-disable-line

  const discovery = useMutation({ mutationFn: api.runDiscovery, onSuccess: setTask });
  const analyze = useMutation({ mutationFn: api.analyzePosts, onSuccess: setTask });
  const regen = useMutation({
    mutationFn: ({ postId, kind }: { postId: string; kind: "comment" | "repost_with_comment" }) =>
      api.regenerate(postId, kind),
    onSuccess: setTask,
  });
  const regeneratingPostId = regen.isPending ? regen.variables?.postId ?? null : null;
  const busy = discovery.isPending || analyze.isPending;

  return (
    <div className="space-y-6">
      {notice && (
        <p className="rounded-xl border border-brand/30 bg-brand/5 px-4 py-3 text-[13px] text-brand">{notice}</p>
      )}

      {loading && <SkeletonBlock label="Carico i profili collegati…" />}
      {!loading && !active && <EmptyState onAdd={openAdd} />}

      {active && (
        <>
          <KnowledgeBaseCard connection={active} onChanged={refreshConnections} />
          <ViralFilters
            key={active.id}
            geoOptions={meta?.geo_options ?? DEFAULT_GEO}
            provider={meta?.discovery_provider ?? "free"}
            running={discovery.isPending}
            analyzing={analyze.isPending}
            onRun={(f) =>
              discovery.mutate({
                connection_id: active.id,
                niche: f.niche,
                keywords_primary: f.primary,
                keywords_secondary: f.secondary,
                geo: f.geo,
                limit: 10,
                variants_per_post: 2,
              })
            }
            onAnalyze={(niche, text, author) =>
              analyze.mutate({
                connection_id: active.id,
                niche: niche || "Manuale",
                variants_per_post: 2,
                posts: [{ text, author_name: author || undefined }],
              })
            }
          />

          {(discovery.isError || analyze.isError) && (
            <p className="rounded-xl border border-warn/30 bg-warn/5 px-4 py-3 text-[13px] text-warn">
              {((discovery.error || analyze.error) as Error).message}
            </p>
          )}

          {busy && <SkeletonBlock label="Luka sta analizzando e generando le risposte…" />}

          {task && (
            <ResultsFeed
              task={task}
              regeneratingPostId={regeneratingPostId}
              onRegen={(postId, kind) => regen.mutate({ postId, kind })}
            />
          )}

          {!task && !busy && (
            <p className="rounded-2xl border border-dashed border-line bg-surface px-5 py-10 text-center text-[13px] text-ink-soft">
              Imposta nicchia e area geografica, poi avvia <b>Cerca Post Virali</b> — oppure incolla un post.
            </p>
          )}
        </>
      )}
    </div>
  );
}

/* ---------- Knowledge base ---------- */
function KnowledgeBaseCard({ connection, onChanged }: { connection: Connection; onChanged: () => void }) {
  const upload = useMutation({
    mutationFn: (file: File) => api.uploadDocument(connection.id, file),
    onSuccess: onChanged,
  });
  const reanalyze = useMutation({ mutationFn: () => api.reanalyze(connection.id), onSuccess: onChanged });
  const bp = connection.brand_profile;
  let fileEl: HTMLInputElement | null = null;

  return (
    <Card
      title="Knowledge Base di Luka"
      right={
        <div className="flex items-center gap-2">
          <button
            onClick={() => reanalyze.mutate()}
            disabled={reanalyze.isPending}
            className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium hover:border-line-strong disabled:opacity-50"
          >
            {reanalyze.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Rianalizza
          </button>
          <button
            onClick={() => fileEl?.click()}
            disabled={upload.isPending}
            className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium hover:border-line-strong disabled:opacity-50"
          >
            {upload.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
            Aggiungi PDF/Documenti
          </button>
          <input
            ref={(el) => (fileEl = el)}
            type="file"
            hidden
            accept=".pdf,.docx,.txt,.md"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload.mutate(f);
              e.target.value = "";
            }}
          />
        </div>
      }
    >
      <p className="-mt-2 mb-3 text-xs text-ink-soft">
        Sintesi da profilo LinkedIn e documenti caricati{bp?.generated_by_model ? ` · ${bp.generated_by_model}` : ""}
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <KbItem label="Mission & Value Prop" value={joinTwo(bp?.mission, bp?.value_proposition)} />
        <KbItem label="Market Context & ICP" value={joinTwo(bp?.icp, bp?.market_context)} />
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-md bg-surface-sunken px-2 py-1 text-[11px] text-ink-soft">
          <Link2 className="h-3 w-3" /> Profilo LinkedIn
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-md bg-surface-sunken px-2 py-1 text-[11px] text-ink-soft">
          <FileText className="h-3 w-3" /> {connection.documents_count} documenti
        </span>
        {bp?.tone_of_voice && (
          <span className="inline-flex items-center gap-1.5 rounded-md bg-surface-sunken px-2 py-1 text-[11px] text-ink-soft">
            <Bot className="h-3 w-3" /> tono: {bp.tone_of_voice}
          </span>
        )}
        {upload.isError && <span className="text-[11px] text-warn">{(upload.error as Error).message}</span>}
      </div>
    </Card>
  );
}

function KbItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface-muted p-3.5">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">{label}</p>
      <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">{value || "—"}</p>
    </div>
  );
}

/* ---------- Filtri ricerca ---------- */
function ViralFilters({
  geoOptions,
  provider,
  running,
  analyzing,
  onRun,
  onAnalyze,
}: {
  geoOptions: { value: Geo; label: string }[];
  provider: string;
  running: boolean;
  analyzing: boolean;
  onRun: (f: { niche: string; primary: string[]; secondary: string[]; geo: Geo }) => void;
  onAnalyze: (niche: string, text: string, author: string) => void;
}) {
  const [niche, setNiche] = useState("AI B2B / Sales Intelligence");
  const [primary, setPrimary] = useState("sales, automation, icp, outbound");
  const [secondary, setSecondary] = useState("revops, pipeline, forecast");
  const [geo, setGeo] = useState<Geo>("italy");
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");
  const [pasteAuthor, setPasteAuthor] = useState("");

  return (
    <Card
      title="Ricerca post virali"
      right={<span className="text-[11px] text-ink-faint">fonte: {PROVIDER_LABEL[provider] ?? provider}</span>}
    >
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-[1.2fr_1.2fr_1fr_190px_auto] lg:items-end">
        <Field label="Nicchia">
          <input value={niche} onChange={(e) => setNiche(e.target.value)} className="input" placeholder="es. AI B2B" />
        </Field>
        <Field label="Keyword primarie">
          <input value={primary} onChange={(e) => setPrimary(e.target.value)} className="input" placeholder="separate da virgola" />
        </Field>
        <Field label="Keyword secondarie">
          <input value={secondary} onChange={(e) => setSecondary(e.target.value)} className="input" placeholder="separate da virgola" />
        </Field>
        <Field label="Area geografica">
          <div className="relative">
            <Globe2 className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
            <select value={geo} onChange={(e) => setGeo(e.target.value as Geo)} className="input appearance-none pl-8 pr-8">
              {geoOptions.map((g) => (
                <option key={g.value} value={g.value}>{g.label}</option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint" />
          </div>
        </Field>
        <button
          onClick={() => onRun({ niche, primary: splitCsv(primary), secondary: splitCsv(secondary), geo })}
          disabled={running}
          className="inline-flex h-[38px] items-center justify-center gap-2 rounded-lg bg-brand px-4 text-[13px] font-medium text-white transition hover:bg-brand-hover disabled:opacity-60"
        >
          {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          Cerca Post Virali
        </button>
      </div>

      <div className="mt-3 border-t border-line pt-3">
        <button
          onClick={() => setPasteOpen((v) => !v)}
          className="flex items-center gap-1.5 text-[12px] font-medium text-brand hover:text-brand-hover"
        >
          <ChevronDown className={clsx("h-3.5 w-3.5 transition", pasteOpen && "rotate-180")} />
          Oppure incolla un post di LinkedIn (100% preciso)
        </button>
        {pasteOpen && (
          <div className="mt-3 space-y-2">
            <input
              value={pasteAuthor}
              onChange={(e) => setPasteAuthor(e.target.value)}
              className="input"
              placeholder="Autore del post (facoltativo)"
            />
            <textarea
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              className="input min-h-[110px] resize-y"
              placeholder="Incolla qui il testo del post…"
            />
            <button
              onClick={() => onAnalyze(niche, pasteText.trim(), pasteAuthor.trim())}
              disabled={analyzing || pasteText.trim().length < 20}
              className="inline-flex items-center gap-2 rounded-lg bg-brand-tech px-4 py-2 text-[13px] font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              {analyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              Analizza con Luka
            </button>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ---------- Feed risultati ---------- */
function ResultsFeed({
  task,
  regeneratingPostId,
  onRegen,
}: {
  task: TaskDetail;
  regeneratingPostId: string | null;
  onRegen: (postId: string, kind: "comment" | "repost_with_comment") => void;
}) {
  const s = task.result_summary ?? {};
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">
          Post virali scoperti <span className="text-ink-faint">· {task.posts.length}/10</span>
        </h2>
        <p className="text-[11px] text-ink-faint">
          fonte: {String(s.provider ?? "—")} · {String(s.comments_generated ?? 0)} risposte generate
        </p>
      </div>
      {task.posts.map((p) => (
        <ViralPostCard
          key={p.id}
          post={p}
          onRegen={(kind) => onRegen(p.id, kind)}
          regenerating={regeneratingPostId === p.id}
        />
      ))}
      {task.posts.length === 0 && (
        <p className="rounded-2xl border border-dashed border-line bg-surface px-5 py-10 text-center text-[13px] text-ink-soft">
          Nessun post trovato per questa nicchia. Prova keyword diverse o un'area più ampia.
        </p>
      )}
    </section>
  );
}

function ViralPostCard({
  post,
  onRegen,
  regenerating,
}: {
  post: DiscoveredPost;
  onRegen: (kind: "comment" | "repost_with_comment") => void;
  regenerating: boolean;
}) {
  const comments = post.responses.filter((r) => r.kind === "comment");
  const repost = post.responses.find((r) => r.kind === "repost_with_comment");
  const [tab, setTab] = useState(0);
  const list = repost ? [...comments, repost] : comments;
  const current = list[Math.min(tab, list.length - 1)];

  return (
    <article className="overflow-hidden rounded-2xl border border-line bg-surface shadow-card">
      <div className="grid lg:grid-cols-2">
        <div className="border-b border-line p-5 lg:border-b-0 lg:border-r">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-surface-sunken text-[11px] font-semibold text-ink-soft">
                {post.author_name.slice(0, 2).toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="truncate text-[13px] font-semibold leading-tight">{post.author_name}</p>
                <p className="truncate text-[11px] text-ink-faint">{post.author_headline}</p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <span className="rounded-md bg-brand/5 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-brand">
                #{post.rank}
              </span>
              {post.niche && (
                <span className="rounded-md bg-surface-sunken px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-ink-soft">
                  {post.niche}
                </span>
              )}
            </div>
          </div>

          <p className="mt-3 whitespace-pre-line text-[13px] leading-relaxed text-ink-soft">
            {truncate(post.text_excerpt, 320)}
          </p>

          <div className="mt-4 grid grid-cols-4 gap-2 border-t border-line pt-3 text-[11px] text-ink-faint">
            <Metric label="Score" value={post.engagement_score.toFixed(1)} strong />
            <Metric label="Reaction" value={fmt(post.reactions)} />
            <Metric label="Commenti" value={fmt(post.comments)} />
            <Metric label="Views" value={post.views ? fmt(post.views) : "n/d"} />
          </div>
          {post.author_profile_url && (
            <a
              href={post.linkedin_post_url}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-[11px] text-ink-faint hover:text-brand"
            >
              <ExternalLink className="h-3 w-3" /> vedi il post originale
            </a>
          )}
        </div>

        <div className="bg-surface-muted p-5">
          <div className="mb-2.5 flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-brand">
              <Sparkles className="h-3.5 w-3.5" /> Risposta di Luka
            </span>
            <span className="rounded-md border border-line bg-surface px-1.5 py-0.5 text-[10px] text-ink-soft">
              {current?.model === "demo" ? "template" : current?.model}
            </span>
          </div>

          {list.length > 1 && (
            <div className="mb-2.5 flex flex-wrap gap-1.5">
              {list.map((r, i) => (
                <button
                  key={r.id}
                  onClick={() => setTab(i)}
                  className={clsx(
                    "rounded-md border px-2 py-1 text-[11px] font-medium transition",
                    i === tab
                      ? "border-brand bg-brand/5 text-brand"
                      : "border-line bg-surface text-ink-soft hover:border-line-strong",
                  )}
                >
                  {r.kind === "repost_with_comment" ? "Repost + commento" : `Commento ${i + 1}`}
                </button>
              ))}
            </div>
          )}

          {current ? (
            <>
              <div className="rounded-xl border border-line bg-surface p-3.5 text-[13px] leading-relaxed text-ink">
                <p className="whitespace-pre-line">{current.body}</p>
                {current.hook_type && (
                  <p className="mt-2.5 border-t border-line pt-2 text-[11px] text-ink-faint">
                    <b className="font-semibold text-ink-soft">hook {current.hook_type}</b>
                    {current.rationale ? ` — ${current.rationale}` : ""}
                  </p>
                )}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  onClick={() => onRegen(current.kind)}
                  disabled={regenerating}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium hover:border-line-strong disabled:opacity-50"
                >
                  {regenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                  Rigenera
                </button>
                <CopyButton text={current.body} />
                <a
                  href={current.deeplink_url ?? post.linkedin_post_url}
                  target="_blank"
                  rel="noreferrer"
                  className="ml-auto inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-hover"
                >
                  <ExternalLink className="h-3.5 w-3.5" /> Apri su LinkedIn
                </a>
              </div>
            </>
          ) : (
            <p className="rounded-xl border border-dashed border-line bg-surface px-3 py-6 text-center text-[12px] text-ink-faint">
              Nessuna risposta: post fuori nicchia o senza aggancio.
            </p>
          )}
        </div>
      </div>
    </article>
  );
}

function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="rounded-2xl border border-dashed border-line bg-surface px-6 py-16 text-center">
      <div className="mx-auto grid h-10 w-10 place-items-center rounded-xl bg-brand/5 text-brand">
        <Link2 className="h-5 w-5" />
      </div>
      <h2 className="mt-3 text-sm font-semibold">Nessun profilo collegato</h2>
      <p className="mx-auto mt-1 max-w-sm text-[13px] text-ink-soft">
        Collega un profilo personale o una Pagina aziendale per far partire l'onboarding di Luka.
      </p>
      <button
        onClick={onAdd}
        className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-brand px-4 py-2 text-[13px] font-semibold text-white hover:bg-brand-hover"
      >
        <Plus className="h-4 w-4" /> Collega profilo
      </button>
    </div>
  );
}
