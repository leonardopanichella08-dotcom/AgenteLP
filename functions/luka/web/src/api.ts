import type { Connection, KbDocument, Meta, TaskDetail, TaskSummary } from "./types";

const BASE = import.meta.env.VITE_API_BASE || "";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: init?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  meta: () => req<Meta>("/api/meta"),

  connections: () => req<Connection[]>("/api/connections"),
  createConnection: (body: {
    account_type: string;
    display_name: string;
    headline?: string;
    industry?: string;
    vanity_url?: string;
    raw_about?: string;
  }) => req<Connection>("/api/connections", { method: "POST", body: JSON.stringify(body) }),
  reanalyze: (id: string) =>
    req<Connection>(`/api/connections/${id}/reanalyze`, { method: "POST" }),

  documents: (connId: string) =>
    req<KbDocument[]>(`/api/connections/${connId}/documents`),
  uploadDocument: (connId: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return req<KbDocument>(`/api/connections/${connId}/documents`, { method: "POST", body: fd });
  },
  deleteDocument: (connId: string, docId: string) =>
    req<void>(`/api/connections/${connId}/documents/${docId}`, { method: "DELETE" }),
  deleteConnection: (id: string) =>
    req<void>(`/api/connections/${id}`, { method: "DELETE" }),

  tasks: () => req<TaskSummary[]>("/api/tasks"),

  runDiscovery: (body: {
    connection_id: string;
    niche: string;
    keywords_primary: string[];
    keywords_secondary: string[];
    geo: string;
    limit: number;
    variants_per_post: number;
  }) => req<TaskDetail>("/api/tasks/discovery", { method: "POST", body: JSON.stringify(body) }),

  analyzePosts: (body: {
    connection_id: string;
    niche: string;
    variants_per_post: number;
    posts: {
      text: string;
      author_name?: string;
      author_headline?: string;
      url?: string;
      reactions?: number;
      comments?: number;
    }[];
  }) => req<TaskDetail>("/api/tasks/analyze", { method: "POST", body: JSON.stringify(body) }),

  task: (id: string) => req<TaskDetail>(`/api/tasks/${id}`),
  regenerate: (postId: string, kind: "comment" | "repost_with_comment") =>
    req<TaskDetail>(`/api/tasks/posts/${postId}/regenerate`, {
      method: "POST",
      body: JSON.stringify({ kind }),
    }),
};
