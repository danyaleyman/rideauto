"use client";

import { getPublicApiBase } from "@/lib/env";

export function readAdminKey(): string {
  return "";
}

export function writeAdminKey(_key: string) {
  // session-based admin; no local key storage
}

export type LeadAdminRow = {
  id: number;
  full_name: string;
  contact_method: string;
  message: string;
  email_sent: boolean;
  created_at: string | null;
};

export async function fetchLeadsAdmin(
  options?: { signal?: AbortSignal },
): Promise<{ result: LeadAdminRow[]; total: number }> {
  const base = getPublicApiBase();
  const res = await fetch(`${base}/api/leads/admin?limit=100`, {
    cache: "no-store",
    credentials: "include",
    headers: { Accept: "application/json" },
    signal: options?.signal,
  });
  if (res.status === 401 || res.status === 403) {
    throw new Error(String(res.status));
  }
  if (!res.ok) throw new Error(`${res.status}`);
  return (await res.json()) as { result: LeadAdminRow[]; total: number };
}
