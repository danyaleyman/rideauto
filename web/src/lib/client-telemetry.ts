"use client";

type TelemetryPayload = Record<string, unknown>;

const SESSION_KEY = "wra_client_session_id";

function randomId(): string {
  const arr = new Uint8Array(16);
  crypto.getRandomValues(arr);
  return Array.from(arr, (b) => b.toString(16).padStart(2, "0")).join("");
}

function getSessionId(): string {
  if (typeof window === "undefined") return "server";
  try {
    const saved = window.localStorage.getItem(SESSION_KEY);
    if (saved && saved.trim()) return saved;
    const sid = randomId();
    window.localStorage.setItem(SESSION_KEY, sid);
    return sid;
  } catch {
    return randomId();
  }
}

export function sendClientEvent(eventType: string, payload: TelemetryPayload = {}): void {
  if (typeof window === "undefined") return;
  if (!eventType.trim()) return;

  const bodyObj = {
    session_id: getSessionId(),
    event_type: eventType.slice(0, 64),
    payload,
    pathname: window.location.pathname + window.location.search,
    user_agent: navigator.userAgent,
  };
  const body = JSON.stringify(bodyObj);
  const url = "/api/web-events";
  try {
    if (navigator.sendBeacon) {
      const blob = new Blob([body], { type: "application/json" });
      navigator.sendBeacon(url, blob);
      return;
    }
  } catch {
    // fallthrough to fetch
  }
  void fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
    cache: "no-store",
  }).catch(() => {});
}

