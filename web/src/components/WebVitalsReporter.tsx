"use client";

import { useEffect } from "react";
import { useReportWebVitals } from "next/web-vitals";

type VitalMetric = {
  id: string;
  name: string;
  value: number;
  rating?: string;
  delta?: number;
  navigationType?: string;
};

function sendMetric(metric: VitalMetric) {
  if (typeof window === "undefined") return;
  if (process.env.NODE_ENV !== "production") return;

  const payload = JSON.stringify({
    id: metric.id,
    name: metric.name,
    value: metric.value,
    rating: metric.rating ?? null,
    delta: metric.delta ?? null,
    navigation_type: metric.navigationType ?? null,
    pathname: window.location.pathname,
    user_agent: navigator.userAgent,
  });

  const url = "/api/web-vitals";
  const body = new Blob([payload], { type: "application/json" });
  if (navigator.sendBeacon) {
    navigator.sendBeacon(url, body);
    return;
  }
  void fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload,
    keepalive: true,
  });
}

function sendClientRuntimeEvent(eventType: string, payload: Record<string, unknown>) {
  if (typeof window === "undefined") return;
  const body = JSON.stringify({
    session_id: `runtime-${Date.now()}`,
    event_type: eventType,
    payload,
    pathname: window.location.pathname + window.location.search,
    user_agent: navigator.userAgent,
  });
  const blob = new Blob([body], { type: "application/json" });
  if (navigator.sendBeacon) {
    navigator.sendBeacon("/api/web-events", blob);
    return;
  }
  void fetch("/api/web-events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
  }).catch(() => {});
}

export default function WebVitalsReporter() {
  useEffect(() => {
    const onError = (e: ErrorEvent) => {
      sendClientRuntimeEvent("client_error", {
        message: e.message || "unknown error",
        source: e.filename || null,
        line: e.lineno || null,
        col: e.colno || null,
      });
    };
    const onRejection = (e: PromiseRejectionEvent) => {
      const reason =
        typeof e.reason === "string"
          ? e.reason
          : (e.reason && typeof e.reason.message === "string" && e.reason.message) || "unhandled rejection";
      sendClientRuntimeEvent("client_unhandled_rejection", { reason: String(reason).slice(0, 400) });
    };
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
    };
  }, []);

  useReportWebVitals((metric) => {
    sendMetric(metric as VitalMetric);
  });
  return null;
}
