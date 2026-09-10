import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Circle, ExternalLink } from "lucide-react";
import { api } from "../api";
import { useApp } from "../state";
import { Card, Pill } from "../ui";

export default function SettingsPage() {
  const { meta } = useApp();
  const authQ = useQuery({
    queryKey: ["linkedin-status"],
    queryFn: async () => {
      const r = await fetch("/api/auth/linkedin/status");
      return r.ok ? ((await r.json()) as { configured: boolean; scopes: string[]; redirect_uri: string }) : null;
    },
  });

  const genOn = meta?.generation_mode === "llm";
  const discovery = meta?.discovery_provider ?? "—";
  const oauthOn = meta?.linkedin_oauth ?? false;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Settings</h1>
        <p className="text-[13px] text-ink-soft">
          Configurazione dell'agente. I valori si impostano come variabili d'ambiente (in locale nel file <code>.env</code>, in produzione su Vercel).
        </p>
      </div>

      <Card title="Generazione AI">
        <Row
          on={genOn}
          title={genOn ? `Attiva — ${meta?.llm_provider} (${meta?.model})` : "Demo mode (risposte da template)"}
          desc={
            genOn
              ? "I commenti e i repost sono scritti da un modello linguistico usando la tua knowledge base."
              : "Imposta GEMINI_API_KEY (gratis, da aistudio.google.com) o ANTHROPIC_API_KEY per la generazione reale."
          }
        />
      </Card>

      <Card title="Discovery post virali">
        <Row
          on={discovery === "apify"}
          title={
            discovery === "apify"
              ? "LinkedIn reale via Apify"
              : discovery === "free"
                ? "Segnale di nicchia (Hacker News)"
                : "Dataset locale"
          }
          desc={
            discovery === "apify"
              ? "Scraping di post LinkedIn reali per keyword. Consuma crediti Apify."
              : "Per i post LinkedIn reali imposta DISCOVERY_PROVIDER=apify e APIFY_TOKEN."
          }
        />
      </Card>

      <Card title="Login LinkedIn (OAuth)">
        <Row
          on={oauthOn}
          title={oauthOn ? "Configurato — pulsante 'Continua con LinkedIn' attivo" : "Non configurato — inserimento manuale del profilo"}
          desc={
            oauthOn
              ? `Scope: ${authQ.data?.scopes?.join(", ") ?? "openid profile email"}`
              : "Crea un'app su LinkedIn Developers, prodotto 'Sign In with LinkedIn using OpenID Connect', poi imposta LINKEDIN_CLIENT_ID e LINKEDIN_CLIENT_SECRET."
          }
        />
        {authQ.data?.redirect_uri && (
          <p className="mt-3 rounded-lg bg-surface-sunken px-3 py-2 text-[11px] text-ink-soft">
            Redirect URI da registrare: <code className="break-all">{authQ.data.redirect_uri}</code>
          </p>
        )}
        <a
          href="https://www.linkedin.com/developers/apps"
          target="_blank"
          rel="noreferrer"
          className="mt-3 inline-flex items-center gap-1.5 text-[12px] font-medium text-brand"
        >
          <ExternalLink className="h-3.5 w-3.5" /> LinkedIn Developers
        </a>
      </Card>

      <Card title="Aree geografiche disponibili">
        <div className="flex flex-wrap gap-2">
          {(meta?.geo_options ?? []).map((g) => (
            <Pill key={g.value}>{g.label}</Pill>
          ))}
        </div>
      </Card>
    </div>
  );
}

function Row({ on, title, desc }: { on: boolean; title: string; desc: string }) {
  return (
    <div className="flex items-start gap-3">
      {on ? (
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ok" />
      ) : (
        <Circle className="mt-0.5 h-4 w-4 shrink-0 text-ink-faint" />
      )}
      <div>
        <p className="text-[13px] font-medium">{title}</p>
        <p className="mt-0.5 text-[12px] leading-relaxed text-ink-soft">{desc}</p>
      </div>
    </div>
  );
}
