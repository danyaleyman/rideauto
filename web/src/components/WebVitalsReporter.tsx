"use client";

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

export default function WebVitalsReporter() {
  useReportWebVitals((metric) => {
    sendMetric(metric as VitalMetric);
  });
  return null;
}
