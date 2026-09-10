import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import clsx from "clsx";
import { AtSign, ChevronDown, Link2, Loader2, Sparkles, X } from "lucide-react";
import { api } from "../api";
import { useApp } from "../state";
import { Field } from "../ui";

export function AddConnectionModal() {
  const { addOpen, closeAdd, refreshConnections, setActiveId, meta } = useApp();
  const oauth = meta?.linkedin_oauth ?? false;

  const [accountType, setAccountType] = useState<"personal" | "company">("personal");
  const [username, setUsername] = useState("");
  const [manualOpen, setManualOpen] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [headline, setHeadline] = useState("");
  const [industry, setIndustry] = useState("");
  const [rawAbout, setRawAbout] = useState("");

  const onDone = (c: { id: string }) => {
    refreshConnections();
    setActiveId(c.id);
    closeAdd();
  };

  const fromUsername = useMutation({
    mutationFn: () => api.createFromUsername({ username: username.trim(), account_type: accountType }),
    onSuccess: onDone,
  });
  const manual = useMutation({
    mutationFn: () =>
      api.createConnection({
        account_type: accountType,
        display_name: displayName,
        headline,
        industry,
        raw_about: rawAbout,
      }),
    onSuccess: onDone,
  });

  if (!addOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/30 p-0 backdrop-blur-sm sm:items-center sm:p-4">
      <div className="max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-t-2xl border border-line bg-surface p-5 shadow-pop sm:rounded-2xl">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Collega profilo o Pagina</h3>
          <button onClick={closeAdd} className="rounded-md p-1 text-ink-faint hover:bg-surface-muted">
            <X className="h-4 w-4" />
          </button>
        </div>

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
            <a
              href={`/api/auth/linkedin/start?account_type=${accountType}`}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 text-[13px] font-semibold text-white hover:bg-brand-hover"
            >
              <Link2 className="h-4 w-4" /> Continua con LinkedIn
            </a>
          )}

          {/* metodo consigliato: username -> scrape + analisi automatica */}
          <Field
            label="Username LinkedIn"
            hint="La parte finale di linkedin.com/in/… — l'app analizza il profilo e compila tutto."
          >
            <div className="relative">
              <AtSign className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
              <input
                className="input pl-8"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="mario-rossi  oppure  https://linkedin.com/in/mario-rossi"
              />
            </div>
          </Field>
          <button
            onClick={() => fromUsername.mutate()}
            disabled={fromUsername.isPending || username.trim().length < 2}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 text-[13px] font-semibold text-white hover:bg-brand-hover disabled:opacity-50"
          >
            {fromUsername.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {fromUsername.isPending ? "Analizzo il profilo…" : "Analizza profilo e collega"}
          </button>
          {fromUsername.isError && (
            <p className="text-[12px] text-warn">{(fromUsername.error as Error).message}</p>
          )}

          {/* fallback manuale */}
          <button
            onClick={() => setManualOpen((v) => !v)}
            className="flex items-center gap-1.5 pt-1 text-[12px] font-medium text-ink-soft hover:text-ink"
          >
            <ChevronDown className={clsx("h-3.5 w-3.5 transition", manualOpen && "rotate-180")} />
            Oppure inserisci i dati a mano
          </button>
          {manualOpen && (
            <div className="space-y-3 border-t border-line pt-3">
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
              {manual.isError && <p className="text-[12px] text-warn">{(manual.error as Error).message}</p>}
              <button
                onClick={() => manual.mutate()}
                disabled={!displayName || manual.isPending}
                className="inline-flex items-center gap-1.5 rounded-lg border border-line px-4 py-1.5 text-[13px] font-semibold hover:border-line-strong disabled:opacity-50"
              >
                {manual.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Collega e analizza
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
