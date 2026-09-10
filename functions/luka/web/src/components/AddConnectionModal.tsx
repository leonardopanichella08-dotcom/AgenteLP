import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import clsx from "clsx";
import { Link2, Loader2, X } from "lucide-react";
import { api } from "../api";
import { useApp } from "../state";
import { Field } from "../ui";

export function AddConnectionModal() {
  const { addOpen, closeAdd, refreshConnections, setActiveId, meta } = useApp();
  const oauth = meta?.linkedin_oauth ?? false;

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
    onSuccess: (c) => {
      refreshConnections();
      setActiveId(c.id);
      closeAdd();
    },
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
        <p className="mt-1 text-[11px] text-ink-soft">
          {oauth
            ? "Collega con LinkedIn, oppure incolla i dati manualmente."
            : "Incolla i dati dal profilo. L'OAuth LinkedIn si attiva quando imposti CLIENT_ID/SECRET."}
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
            onClick={closeAdd}
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
