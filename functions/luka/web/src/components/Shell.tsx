import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import clsx from "clsx";
import {
  Bot,
  ChevronDown,
  CircleCheck,
  LayoutDashboard,
  Link2,
  Plus,
  Settings,
  Sparkles,
} from "lucide-react";
import { useApp } from "../state";
import { AddConnectionModal } from "./AddConnectionModal";

const NAV = [
  { to: "/", label: "Agente Luka", short: "Luka", icon: Bot, dot: true, end: true },
  { to: "/dashboard", label: "Dashboard", short: "Home", icon: LayoutDashboard },
  { to: "/connections", label: "Profili Collegati", short: "Profili", icon: Link2 },
  { to: "/settings", label: "Settings", short: "Settings", icon: Settings },
];

export function Shell() {
  const { connections } = useApp();
  const user = connections[0];

  return (
    <div className="min-h-screen bg-surface-muted font-sans text-ink">
      <div className="mx-auto flex max-w-[1440px]">
        {/* Sidebar desktop */}
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-line bg-surface lg:flex">
          <div className="flex items-center gap-2.5 px-5 py-5">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-brand-tech text-white">
              <Sparkles className="h-4 w-4" />
            </div>
            <span className="text-[15px] font-semibold tracking-tight">AgenteLP</span>
          </div>
          <nav className="flex-1 space-y-1 px-3">
            {NAV.map(({ to, label, icon: Icon, dot, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  clsx(
                    "group flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition",
                    isActive
                      ? "bg-surface-sunken text-ink"
                      : "text-ink-soft hover:bg-surface-muted hover:text-ink",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={clsx(
                        "h-4 w-4",
                        isActive ? "text-brand" : "text-ink-faint group-hover:text-ink-soft",
                      )}
                    />
                    {label}
                    {dot && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-ok" />}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
          <div className="m-3 flex items-center gap-3 rounded-lg border border-line p-3">
            <div className="grid h-8 w-8 place-items-center rounded-full bg-surface-sunken text-[11px] font-semibold text-ink-soft">
              {(user?.display_name ?? "LP").slice(0, 2).toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="truncate text-[13px] font-medium">{user?.display_name ?? "Utente"}</p>
              <p className="truncate text-[11px] text-ink-faint">demo@agentelp.app</p>
            </div>
          </div>
        </aside>

        <main className="min-w-0 flex-1 pb-24 lg:pb-0">
          <Topbar />
          <div className="px-4 py-6 sm:px-6 lg:px-8">
            <Outlet />
          </div>
        </main>
      </div>

      <MobileNav />
      <AddConnectionModal />
    </div>
  );
}

/* ---------- Topbar con selettore profilo ---------- */
function Topbar() {
  const { connections, active, setActiveId, openAdd, meta } = useApp();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const mode = meta?.generation_mode ?? "demo";
  const model = meta?.model ?? null;

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-line bg-surface/85 px-4 py-3 backdrop-blur sm:px-6 lg:px-8">
      <div className="flex items-center gap-2 lg:hidden">
        <Sparkles className="h-4 w-4 text-brand" />
        <span className="text-sm font-semibold">AgenteLP</span>
      </div>

      <div className="relative" ref={ref}>
        <button
          onClick={() => setOpen((v) => !v)}
          disabled={!connections.length}
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
                  setActiveId(c.id);
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
                openAdd();
              }}
              className="mt-1 flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-[13px] font-medium text-brand hover:bg-surface-muted"
            >
              <Plus className="h-4 w-4" /> Collega profilo o pagina
            </button>
          </div>
        )}
      </div>

      <span
        className={clsx(
          "rounded-md border px-1.5 py-0.5 text-[11px] font-medium",
          mode === "llm"
            ? "border-ok/30 bg-ok/5 text-ok"
            : "border-line bg-surface-sunken text-ink-soft",
        )}
        title={mode === "llm" ? `Generazione con ${model}` : "Nessuna API key: risposte template"}
      >
        {mode === "llm" ? model : "demo mode"}
      </span>
    </header>
  );
}

/* ---------- Bottom nav mobile ---------- */
function MobileNav() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 flex items-center justify-around border-t border-line bg-surface/95 px-2 py-2 backdrop-blur lg:hidden">
      {NAV.map(({ to, short, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            clsx(
              "flex flex-1 flex-col items-center gap-1 rounded-lg py-1.5 text-[10px] font-medium",
              isActive ? "text-brand" : "text-ink-faint",
            )
          }
        >
          <Icon className="h-5 w-5" />
          {short}
        </NavLink>
      ))}
    </nav>
  );
}
