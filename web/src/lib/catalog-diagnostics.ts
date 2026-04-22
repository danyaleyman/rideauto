"use client";

import { getPublicApiBase } from "./env";

export type CatalogDiagLevel = "info" | "warn" | "error";

type CatalogDiagPayload = {
  session_id: string;
  event: string;
  level: CatalogDiagLevel;
  pathname?: string;
  market?: string;
  payload: Record<string, unknown>;
};

const SESSION_STORAGE_KEY = "catalog_diag_session_id";

function getSessionId(): string {
  if (typeof window === "undefined") return "server";
  try {
    const existing = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (existing) return existing;
    const created = `diag-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, created);
    return created;
  } catch {
    return `diag-${Date.now()}`;
  }
}

export function isCatalogDiagEnabled(searchParamsString: string): boolean {
  try {
    const qp = new URLSearchParams(searchParamsString);
    return qp.get("diag") === "1";
  } catch {
    return false;
  }
}

export function sendCatalogDiagEvent(
  enabled: boolean,
  event: string,
  data: Record<string, unknown>,
  options?: { level?: CatalogDiagLevel; market?: string; pathname?: string },
): void {
  if (!enabled) return;
  if (typeof window === "undefined") return;

  const payload: CatalogDiagPayload = {
    session_id: getSessionId(),
    event,
    level: options?.level ?? "info",
    market: options?.market,
    pathname: options?.pathname ?? `${window.location.pathname}${window.location.search}`,
    payload: data,
  };

  const base = getPublicApiBase();
  void fetch(`${base}/api/catalog-filter-events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    keepalive: true,
  }).catch(() => {});
}
