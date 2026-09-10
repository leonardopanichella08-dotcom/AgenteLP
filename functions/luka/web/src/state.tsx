import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { Connection, Meta } from "./types";

interface Ctx {
  meta: Meta | undefined;
  connections: Connection[];
  loading: boolean;
  active: Connection | null;
  setActiveId: (id: string) => void;
  refreshConnections: () => void;
  addOpen: boolean;
  openAdd: () => void;
  closeAdd: () => void;
}

const AppCtx = createContext<Ctx | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const metaQ = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  const connQ = useQuery({ queryKey: ["connections"], queryFn: api.connections });

  const conns = connQ.data ?? [];
  const [activeId, setActiveId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);

  useEffect(() => {
    if (!activeId && conns[0]) setActiveId(conns[0].id);
    if (activeId && conns.length && !conns.some((c) => c.id === activeId)) {
      setActiveId(conns[0]?.id ?? null);
    }
  }, [conns, activeId]);

  const active = useMemo(
    () => conns.find((c) => c.id === activeId) ?? conns[0] ?? null,
    [conns, activeId],
  );

  const value: Ctx = {
    meta: metaQ.data,
    connections: conns,
    loading: connQ.isLoading,
    active,
    setActiveId,
    refreshConnections: () => qc.invalidateQueries({ queryKey: ["connections"] }),
    addOpen,
    openAdd: () => setAddOpen(true),
    closeAdd: () => setAddOpen(false),
  };

  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

export function useApp(): Ctx {
  const c = useContext(AppCtx);
  if (!c) throw new Error("useApp fuori da AppProvider");
  return c;
}
