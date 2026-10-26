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

export type TelegramCarStatus = {
  posted: boolean;
  car_id: string;
  posted_at?: string | null;
  message_id?: number | null;
  origin?: string | null;
};

export type TelegramPublishResult = {
  ok: boolean;
  already?: boolean;
  car_id: string;
  posted_at?: string | null;
  message_id?: number | null;
  title?: string;
  mode?: string;
  photos?: number;
};

function telegramErrorMessage(status: number, detail: string): string {
  if (status === 401 || status === 403) return "forbidden";
  if (status === 503 || detail.includes("not_configured")) return "not_configured";
  if (detail.includes("telegram_no_photos")) return "no_photos";
  return "failed";
}

export async function fetchCarTelegramStatus(
  carId: string,
  options?: { signal?: AbortSignal },
): Promise<TelegramCarStatus> {
  const base = getPublicApiBase();
  const res = await fetch(`${base}/api/telegram/channel/cars/${encodeURIComponent(carId)}`, {
    cache: "no-store",
    credentials: "include",
    headers: { Accept: "application/json" },
    signal: options?.signal,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(telegramErrorMessage(res.status, body));
  }
  return (await res.json()) as TelegramCarStatus;
}

export async function publishCarToTelegram(
  carId: string,
  payload: { text?: string; photo_urls?: string[]; force?: boolean },
): Promise<TelegramPublishResult> {
  const base = getPublicApiBase();
  const res = await fetch(`${base}/api/telegram/channel/cars/${encodeURIComponent(carId)}`, {
    method: "POST",
    cache: "no-store",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });
  const body = await res.text();
  if (!res.ok) {
    throw new Error(telegramErrorMessage(res.status, body));
  }
  return JSON.parse(body) as TelegramPublishResult;
}
