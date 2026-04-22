"use client";

import { useEffect } from "react";
import { useReportWebVitals } from "next/web-vitals";
import { isCatalogDiagEnabled, sendCatalogDiagEvent } from "@/lib/catalog-diagnostics";

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

export default function WebVitalsReporter() {
  useEffect(() => {
    const enabledForCatalog = () =>
      typeof window !== "undefined" &&
      window.location.pathname.startsWith("/catalog") &&
      isCatalogDiagEnabled(window.location.search.replace(/^\?/, ""));

    const onError = (e: ErrorEvent) => {
      if (!enabledForCatalog()) return;
      sendCatalogDiagEvent(
        true,
        "catalog_client_error",
        {
          message: e.message || "unknown",
          source: e.filename || null,
          line: e.lineno || null,
          col: e.colno || null,
        },
        { level: "error" },
      );
    };
    const onUnhandledRejection = (e: PromiseRejectionEvent) => {
      if (!enabledForCatalog()) return;
      const reason =
        typeof e.reason === "string"
          ? e.reason
          : (e.reason && typeof e.reason.message === "string" && e.reason.message) || "unknown";
      sendCatalogDiagEvent(
        true,
        "catalog_unhandled_rejection",
        { reason: String(reason).slice(0, 500) },
        { level: "error" },
      );
    };
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onUnhandledRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onUnhandledRejection);
    };
  }, []);

  useReportWebVitals((metric) => {
    sendMetric(metric as VitalMetric);
  });
  return null;
}
