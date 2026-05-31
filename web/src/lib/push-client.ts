"use client";

import { getPublicApiBase } from "@/lib/env";

function urlBase64ToArrayBuffer(base64String: string): ArrayBuffer {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out.buffer.slice(out.byteOffset, out.byteOffset + out.byteLength);
}

export async function fetchVapidPublicKey(): Promise<string | null> {
  const base = getPublicApiBase();
  try {
    const res = await fetch(`${base}/api/push/vapid-public-key`, { cache: "no-store" });
    if (!res.ok) return null;
    const data = (await res.json()) as { public_key?: string };
    return data.public_key?.trim() || null;
  } catch {
    return null;
  }
}

export async function subscribeToWebPush(): Promise<"ok" | "unsupported" | "denied" | "error"> {
  if (typeof window === "undefined" || !("serviceWorker" in navigator) || !("PushManager" in window)) {
    return "unsupported";
  }
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return "denied";
  const pub = await fetchVapidPublicKey();
  if (!pub) return "error";
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToArrayBuffer(pub),
  });
  const json = sub.toJSON();
  const base = getPublicApiBase();
  const res = await fetch(`${base}/api/push/subscribe`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({
      endpoint: sub.endpoint,
      keys: { p256dh: json.keys?.p256dh, auth: json.keys?.auth },
    }),
  });
  if (!res.ok) return "error";
  return "ok";
}

export async function unsubscribeFromWebPush(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.getSubscription();
  if (!sub) return;
  const base = getPublicApiBase();
  await fetch(`${base}/api/push/subscribe?endpoint=${encodeURIComponent(sub.endpoint)}`, {
    method: "DELETE",
    credentials: "include",
    headers: { Accept: "application/json" },
  }).catch(() => {});
  await sub.unsubscribe();
}

export async function hasActivePushSubscription(): Promise<boolean> {
  if (!("serviceWorker" in navigator)) return false;
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    return Boolean(sub);
  } catch {
    return false;
  }
}
