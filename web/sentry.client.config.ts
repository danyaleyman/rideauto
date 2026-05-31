import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN?.trim();
if (dsn) {
  Sentry.init({
    dsn,
    tracesSampleRate: 0.05,
    replaysOnErrorSampleRate: 0,
    environment: process.env.NODE_ENV,
  });
}
