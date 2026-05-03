"use client";

let sentryReady = false;

/**
 * Отчёт об ошибке с клиента. В проде при ``NEXT_PUBLIC_SENTRY_DSN`` подключается Sentry (лениво).
 */
export function reportClientError(err: unknown, context?: Record<string, unknown>): void {
  if (process.env.NODE_ENV !== "production") {
    console.error("[wra client]", err, context);
  }
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN?.trim();
  if (!dsn || typeof window === "undefined") return;

  void import("@sentry/browser")
    .then((Sentry) => {
      if (!sentryReady) {
        Sentry.init({
          dsn,
          tracesSampleRate: 0.05,
          replaysOnErrorSampleRate: 0,
        });
        sentryReady = true;
      }
      Sentry.captureException(err instanceof Error ? err : new Error(String(err)), {
        extra: context,
      });
    })
    .catch(() => {});
}
