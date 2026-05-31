/**
 * Серверный отчёт ошибок (RSC, instrumentation). DSN: ``SENTRY_DSN`` или ``NEXT_PUBLIC_SENTRY_DSN``.
 */
export function reportServerError(err: unknown, context?: Record<string, unknown>): void {
  if (process.env.NODE_ENV !== "production") {
    console.error("[wra server]", err, context);
  }
  const dsn = process.env.SENTRY_DSN?.trim() || process.env.NEXT_PUBLIC_SENTRY_DSN?.trim();
  if (!dsn) return;

  void import("@sentry/nextjs")
    .then((Sentry) => {
      Sentry.captureException(err instanceof Error ? err : new Error(String(err)), {
        extra: context,
      });
    })
    .catch(() => {});
}
