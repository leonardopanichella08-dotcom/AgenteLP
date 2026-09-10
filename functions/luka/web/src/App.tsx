import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import {
  Bot,
  ChevronDown,
  CircleCheck,
  Copy,
  ExternalLink,
  FileText,
  Globe2,
  LayoutDashboard,
  Link2,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Sparkles,
  X,
} from "lucide-react";
import { api } from "./api";
import type { Connection, DiscoveredPost, GeneratedResponse, Geo, TaskDetail } from "./types";

const NAV = [
  { icon: LayoutDashboard, label: "Dashboard", short: "Dashboard" },
  { icon: Bot, label: "I Miei Agenti", short: "Agenti", active: true, dot: true },
  { icon: Link2, label: "Profili Collegati", short: "Profili" },
  { icon: Settings, label: "Settings", short: "Settings" },
];

export default function App() {
  const qc = useQueryClient();
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  const connections = useQuery({ queryKey: ["connections"], queryFn: api.connections });

  const [activeId, setActiveId] = useState<string | null>(null);
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [showAdd, setShowAdd] = useState(false);

  const conns = connections.data ?? [];
  const active = useMemo(
    () => conns.find((c) => c.id === activeId) ?? conns[0] ?? null,
    [conns, activeId],
  );
  useEffect(() => {
    if (!activeId && conns[0]) setActiveId(conns[0].id);
  }, [conns, activeId]);
  useEffect(() => {
    setTask(null);
  }, [active?.id]);

  // Ritorno dal callback OAuth LinkedIn: ?linkedin=connected&id=... | ?linkedin=error
  const [oauthNotice, setOauthNotice] = useState<string | null>(null);
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const li = p.get("linkedin");
    if (!li) return;
    if (li === "connected") {
      qc.invalidateQueries({ queryKey: ["connections"] });
      const id = p.get("id");
      if (id) setActiveId(id);
      setOauthNotice("Profilo LinkedIn collegato.");
    } else {
      setOauthNotice(`Collegamento LinkedIn non riuscito (${p.get("reason") ?? "errore"}).`);
    }
    window.history.replaceState({}, "", window.location.pathname);
    const t = setTimeout(() => setOauthNotice(null), 4000);
    return () => clearTimeout(t);
  }, [qc]);

  const discovery = useMutation({
    mutationFn: api.runDiscovery,
    onSuccess: (t) => setTask(t),
  });
  const analyze = useMutation({
    mutationFn: api.analyzePosts,
    onSuccess: (t) => setTask(t),
  });
  const regen = useMutation({
    mutationFn: ({ postId, kind }: { postId: string; kind: "comment" | "repost_with_comment" }) =>
      api.regenerate(postId, kind),
    onSuccess: (t) => setTask(t),
  });
  const regeneratingPostId = regen.isPending ? regen.variables?.postId ?? null : null;

  return (
    <div className="min-h-screen bg-surface-muted font-sans text-ink">
      <div className="mx-auto flex max-w-[1440px]">
        <Sidebar user={conns[0]} />
        <main className="min-w-0 flex-1 pb-24 lg:pb-0">
          <Topbar
            connections={conns}
            active={active}
            onSelect={setActiveId}
            onAdd={() => setShowAdd(true)}
            mode={meta.data?.generation_mode ?? "demo"}
            model={meta.data?.model ?? null}
          />

          <div className="space-y-6 px-4 py-6 sm:px-6 lg:px-8">
            {oauthNotice && (
              <p className="rounded-xl border border-brand/30 bg-brand/5 px-4 py-3 text-[13px] text-brand">
                {oauthNotice}
              </p>
            )}
            {connections.isLoading && <SkeletonBlock label="Carico i profili collegati…" />}

            {!connections.isLoading && !active && (
              <EmptyState onAdd={() => setShowAdd(true)} />
            )}

            {active && (
              <>
                <KnowledgeBaseCard
                  connection={active}
                  onChanged={() => qc.invalidateQueries({ queryKey: ["connections"] })}
                />
                <ViralFilters
                  key={active.id}
                  geoOptions={meta.data?.geo_options ?? DEFAULT_GEO}
                  provider={meta.data?.discovery_provider ?? "free"}
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

                {(discovery.isPending || analyze.isPending) && (
                  <SkeletonBlock label="Luka sta analizzando e generando le risposte…" />
                )}

                {task && (
                  <ResultsFeed
                    task={task}
                    regeneratingPostId={regeneratingPostId}
                    onRegen={(postId, kind) => regen.mutate({ postId, kind })}
                  />
                )}

                {!task && !discovery.isPending && (
                  <p className="rounded-2xl border border-dashed border-line bg-surface px-5 py-10 text-center text-[13px] text-ink-soft">
                    Imposta nicchia e area geografica, poi avvia <b>Cerca Post Virali</b>.
                  </p>
                )}
              </>
            )}
          </div>
        </main>
      </div>

      <MobileNav />
      {showAdd && (
        <AddConnectionModal
          oauth={meta.data?.linkedin_oauth ?? false}
          onClose={() => setShowAdd(false)}
          onCreated={(c) => {
            qc.invalidateQueries({ queryKey: ["connections"] });
            setActiveId(c.id);
            setShowAdd(false);
          }}
        />
      )}
    </div>
  );
}

const DEFAULT_GEO: { value: Geo; label: string }[] = [
  { value: "world", label: "Mondo" },
  { value: "europe", label: "Europa" },
  { value: "italy", label: "Italia" },
];

/* ------------------------------------------------------------------ */
/*  Sidebar                                                            */
/* ------------------------------------------------------------------ */
function Sidebar({ user }: { user?: Connection }) {
  return (
    <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-line bg-surface lg:flex">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-brand text-white">
          <Sparkles className="h-4 w-4" />
        </div>
        <span className="text-[15px] font-semibold tracking-tight">Agent OS</span>
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {NAV.map(({ icon: Icon, label, active, dot }) => (
          <a
            key={label}
            className={clsx(
              "group flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition",
              active
                ? "bg-surface-sunken text-ink"
                : "text-ink-soft hover:bg-surface-muted hover:text-ink",
            )}
          >
            <Icon
              className={clsx(
                "h-4 w-4",
                active ? "text-brand" : "text-ink-faint group-hover:text-ink-soft",
              )}
            />
            {label}
            {dot && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-ok" />}
          </a>
        ))}
      </nav>
      <div className="m-3 flex items-center gap-3 rounded-lg border border-line p-3">
        <div className="grid h-8 w-8 place-items-center rounded-full bg-surface-sunken text-[11px] font-semibold text-ink-soft">
          {(user?.display_name ?? "LU").slice(0, 2).toUpperCase()}
        </div>
        <div className="min-w-0">
          <p className="truncate text-[13px] font-medium">{user?.display_name ?? "Utente Demo"}</p>
          <p className="truncate text-[11px] text-ink-faint">demo@luka.app</p>
        </div>
      </div>
    </aside>
  );
}

/* ------------------------------------------------------------------ */
/*  Topbar — selettore profilo LinkedIn attivo                        */
/* ------------------------------------------------------------------ */
function Topbar({
  connections,
  active,
  onSelect,
  onAdd,
  mode,
  model,
}: {
  connections: Connection[];
  active: Connection | null;
  onSelect: (id: string) => void;
  onAdd: () => void;
  mode: "llm" | "demo";
  model: string | null;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-line bg-surface/85 px-4 py-3 backdrop-blur sm:px-6 lg:px-8">
      <div className="flex items-center gap-2 lg:hidden">
        <Sparkles className="h-4 w-4 text-brand" />
        <span className="text-sm font-semibold">Agent OS</span>
      </div>

      <div className="relative" ref={ref}>
        <button
          onClick={() => setOpen((v) => !v)}
          disabled={!active}
          className="flex items-center gap-2.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] font-medium hover:border-line-strong disabled:opacity-50"
        >
          <span className="h-2 w-2 rounded-full bg-ok" />
          <span className="max-w-[42vw] truncate sm:max-w-none">
            {active?.display_name ?? "Nessun profilo"}
          </span>
          {active && (
            <span className="hidden rounded-md bg-surface-sunken px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-ink-soft sm:inline">
              {active.account_type === "company" ? "Pagina" : "Personale"}
            </span>
          )}
          <ChevronDown className="h-3.5 w-3.5 text-ink-faint" />
        </button>

        {open && (
          <div className="absolute left-0 z-30 mt-1.5 w-72 rounded-xl border border-line bg-surface p-1.5 shadow-pop">
            {connections.map((c) => (
              <button
                key={c.id}
                onClick={() => {
                  onSelect(c.id);
                  setOpen(false);
                }}
                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] hover:bg-surface-muted"
              >
                <span className="h-2 w-2 shrink-0 rounded-full bg-ok" />
                <span className="flex-1 truncate">{c.display_name}</span>
                <span className="text-[10px] uppercase tracking-wide text-ink-faint">
                  {c.account_type === "company" ? "Pagina" : "Personale"}
                </span>
                {c.id === active?.id && <CircleCheck className="h-4 w-4 text-brand" />}
              </button>
            ))}
            <button
              onClick={() => {
                setOpen(false);
                onAdd();
              }}
              className="mt-1 flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-[13px] font-medium text-brand hover:bg-surface-muted"
            >
              <Plus className="h-4 w-4" /> Collega profilo o pagina
            </button>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 text-[11px] text-ink-faint">
        <span className="hidden sm:inline">
          Agente <span className="font-semibold text-ink">Luka</span>
        </span>
        <span
          className={clsx(
            "rounded-md border px-1.5 py-0.5 font-medium",
            mode === "llm"
              ? "border-ok/30 bg-ok/5 text-ok"
              : "border-line bg-surface-sunken text-ink-soft",
          )}
          title={mode === "llm" ? `Generazione con ${model}` : "Nessuna API key: risposte template"}
        >
          {mode === "llm" ? model : "demo mode"}
        </span>
      </div>
    </header>
  );
}

/* ------------------------------------------------------------------ */
/*  Knowledge Base card                                                */
/* ------------------------------------------------------------------ */
function KnowledgeBaseCard({
  connection,
  onChanged,
}: {
  connection: Connection;
  onChanged: () => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const upload = useMutation({
    mutationFn: (file: File) => api.uploadDocument(connection.id, file),
    onSuccess: onChanged,
  });
  const reanalyze = useMutation({
    mutationFn: () => api.reanalyze(connection.id),
    onSuccess: onChanged,
  });
  const bp = connection.brand_profile;

  return (
    <section className="rounded-2xl border border-line bg-surface p-5 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">Knowledge Base di Luka</h2>
          <p className="mt-0.5 text-xs text-ink-soft">
            Sintesi da profilo LinkedIn e documenti caricati
            {bp?.generated_by_model ? ` · ${bp.generated_by_model}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => reanalyze.mutate()}
            disabled={reanalyze.isPending}
            className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium hover:border-line-strong disabled:opacity-50"
          >
            {reanalyze.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            Rianalizza
          </button>
          <button
            onClick={() => fileRef.current?.click()}
            disabled={upload.isPending}
            className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium hover:border-line-strong disabled:opacity-50"
          >
            {upload.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Plus className="h-3.5 w-3.5" />
            )}
            Aggiungi PDF/Documenti
          </button>
          <input
            ref={fileRef}
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
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
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
        {upload.isError && (
          <span className="text-[11px] text-warn">{(upload.error as Error).message}</span>
        )}
      </div>
    </section>
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

/* ------------------------------------------------------------------ */
/*  Filtri ricerca virale                                              */
/* ------------------------------------------------------------------ */
const PROVIDER_LABEL: Record<string, string> = {
  free: "Hacker News + Reddit (gratis)",
  sample: "dataset locale",
  apify: "LinkedIn via Apify",
};

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
    <section className="rounded-2xl border border-line bg-surface p-5 shadow-card">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Ricerca post virali</h2>
        <span className="text-[11px] text-ink-faint">
          fonte: {PROVIDER_LABEL[provider] ?? provider}
        </span>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-[1.2fr_1.2fr_1fr_190px_auto] lg:items-end">
        <Field label="Nicchia">
          <input
            value={niche}
            onChange={(e) => setNiche(e.target.value)}
            className="input"
            placeholder="es. AI B2B"
          />
        </Field>
        <Field label="Keyword primarie">
          <input
            value={primary}
            onChange={(e) => setPrimary(e.target.value)}
            className="input"
            placeholder="separate da virgola"
          />
        </Field>
        <Field label="Keyword secondarie">
          <input
            value={secondary}
            onChange={(e) => setSecondary(e.target.value)}
            className="input"
            placeholder="separate da virgola"
          />
        </Field>
        <Field label="Area geografica">
          <div className="relative">
            <Globe2 className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
            <select
              value={geo}
              onChange={(e) => setGeo(e.target.value as Geo)}
              className="input appearance-none pl-8 pr-8"
            >
              {geoOptions.map((g) => (
                <option key={g.value} value={g.value}>
                  {g.label}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint" />
          </div>
        </Field>
        <button
          onClick={() =>
            onRun({
              niche,
              primary: splitCsv(primary),
              secondary: splitCsv(secondary),
              geo,
            })
          }
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
          <ChevronDown
            className={clsx("h-3.5 w-3.5 transition", pasteOpen && "rotate-180")}
          />
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
              className="inline-flex items-center gap-2 rounded-lg bg-ink px-4 py-2 text-[13px] font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              {analyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              Analizza con Luka
            </button>
          </div>
        )}
      </div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
        {label}
      </span>
      {children}
    </label>
  );
}

/* ------------------------------------------------------------------ */
/*  Feed risultati                                                     */
/* ------------------------------------------------------------------ */
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
          Post virali scoperti{" "}
          <span className="text-ink-faint">· {task.posts.length}/10</span>
        </h2>
        <p className="text-[11px] text-ink-faint">
          fonte: {String(s.provider ?? "sample")} · {String(s.comments_generated ?? 0)} risposte generate
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
        {/* Parte 1 — dettagli del post */}
        <div className="border-b border-line p-5 lg:border-b-0 lg:border-r">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-surface-sunken text-[11px] font-semibold text-ink-soft">
                {post.author_name.slice(0, 2).toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="truncate text-[13px] font-semibold leading-tight">
                  {post.author_name}
                </p>
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
        </div>

        {/* Parte 2 — Luka Engine */}
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
                  {regenerating ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <RefreshCw className="h-3.5 w-3.5" />
                  )}
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

function Metric({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <span className="flex flex-col">
      <span className={clsx("text-[13px] font-semibold", strong ? "text-brand" : "text-ink")}>
        {value}
      </span>
      <span className="text-[10px] uppercase tracking-wide">{label}</span>
    </span>
  );
}

function CopyButton({ text }: { text: string }) {
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
      {done ? "Copiato" : "Copia"}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  Add connection modal                                               */
/* ------------------------------------------------------------------ */
function AddConnectionModal({
  oauth,
  onClose,
  onCreated,
}: {
  oauth: boolean;
  onClose: () => void;
  onCreated: (c: Connection) => void;
}) {
  const [accountType, setAccountType] = useState<"personal" | "company">("personal");
  const [displayName, setDisplayName] = useState("");
  const [headline, setHeadline] = useState("");
  const [industry, setIndustry] = useState("");
  const [rawAbout, setRawAbout] = useState("");

  const create = useMutation({
    mutationFn: () =>
      api.createConnection({
        account_type: accountType,
        display_name: displayName,
        headline,
        industry,
        raw_about: rawAbout,
      }),
    onSuccess: onCreated,
  });

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/30 p-0 backdrop-blur-sm sm:items-center sm:p-4">
      <div className="w-full max-w-lg rounded-t-2xl border border-line bg-surface p-5 shadow-pop sm:rounded-2xl">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Collega profilo o Pagina</h3>
          <button onClick={onClose} className="rounded-md p-1 text-ink-faint hover:bg-surface-muted">
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-1 text-[11px] text-ink-soft">
          {oauth
            ? "Collega con LinkedIn, oppure incolla i dati manualmente."
            : "Incolla i dati dal profilo. Configura l'OAuth LinkedIn per il collegamento automatico."}
        </p>

        <div className="mt-4 space-y-3">
          <div className="flex gap-2">
            {(["personal", "company"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setAccountType(t)}
                className={clsx(
                  "flex-1 rounded-lg border px-3 py-2 text-[13px] font-medium",
                  accountType === t
                    ? "border-brand bg-brand/5 text-brand"
                    : "border-line text-ink-soft hover:border-line-strong",
                )}
              >
                {t === "personal" ? "Profilo personale" : "Pagina aziendale"}
              </button>
            ))}
          </div>

          {oauth && (
            <>
              <a
                href={`/api/auth/linkedin/start?account_type=${accountType}`}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 text-[13px] font-semibold text-white hover:bg-brand-hover"
              >
                <Link2 className="h-4 w-4" /> Continua con LinkedIn
              </a>
              <div className="flex items-center gap-3 py-1 text-[11px] text-ink-faint">
                <span className="h-px flex-1 bg-line" /> oppure manualmente{" "}
                <span className="h-px flex-1 bg-line" />
              </div>
            </>
          )}

          <Field label="Nome visualizzato">
            <input className="input" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          </Field>
          <Field label="Headline">
            <input className="input" value={headline} onChange={(e) => setHeadline(e.target.value)} />
          </Field>
          <Field label="Settore / Industry">
            <input className="input" value={industry} onChange={(e) => setIndustry(e.target.value)} />
          </Field>
          <Field label="Bio / esperienze / descrizione azienda">
            <textarea
              className="input min-h-[90px] resize-y"
              value={rawAbout}
              onChange={(e) => setRawAbout(e.target.value)}
            />
          </Field>
          {create.isError && (
            <p className="text-[12px] text-warn">{(create.error as Error).message}</p>
          )}
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg border border-line px-3 py-1.5 text-[13px] font-medium hover:border-line-strong"
          >
            Annulla
          </button>
          <button
            onClick={() => create.mutate()}
            disabled={!displayName || create.isPending}
            className="inline-flex items-center gap-1.5 rounded-lg bg-brand px-4 py-1.5 text-[13px] font-semibold text-white hover:bg-brand-hover disabled:opacity-50"
          >
            {create.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Collega e analizza
          </button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Misc                                                               */
/* ------------------------------------------------------------------ */
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

function SkeletonBlock({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-line bg-surface px-5 py-6 text-[13px] text-ink-soft shadow-card">
      <Loader2 className="h-4 w-4 animate-spin text-brand" />
      {label}
    </div>
  );
}

function MobileNav() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 flex items-center justify-around border-t border-line bg-surface/95 px-2 py-2 backdrop-blur lg:hidden">
      {NAV.map(({ icon: Icon, short, active }) => (
        <a
          key={short}
          className={clsx(
            "flex flex-1 cursor-pointer flex-col items-center gap-1 rounded-lg py-1.5 text-[10px] font-medium",
            active ? "text-brand" : "text-ink-faint",
          )}
        >
          <Icon className="h-5 w-5" />
          {short}
        </a>
      ))}
    </nav>
  );
}

/* helpers */
function splitCsv(s: string): string[] {
  return s
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}
function joinTwo(a?: string | null, b?: string | null): string {
  return [a, b].filter(Boolean).join(" ");
}
function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n).trimEnd()}…` : s;
}
function fmt(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`;
  return String(n);
}
