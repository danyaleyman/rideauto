"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useLocaleContext } from "@/components/LocaleProvider";
import { Button } from "@/components/ui/button";
import { fetchLeadsAdmin, type LeadAdminRow } from "@/lib/admin-api";

export function AdminLeadsClient() {
  const { t } = useLocaleContext();
  const router = useRouter();
  const { authenticated, loading: authLoading } = useAuth();
  const [rows, setRows] = useState<LeadAdminRow[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchLeadsAdmin();
      setRows(data.result);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "";
      if (msg.includes("403") || msg.includes("401")) {
        setError(t("admin.forbidden"));
      } else {
        setError(t("admin.loadError"));
      }
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (!authLoading && !authenticated) {
      router.replace("/login?next=/admin/leads");
      return;
    }
    if (authenticated) void load();
  }, [authLoading, authenticated, load, router]);

  if (authLoading) {
    return <main className="px-4 py-16 text-sm text-muted-foreground">{t("account.loading")}</main>;
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{t("admin.leadsTitle")}</h1>
        <Button variant="outline" size="sm" className="rounded-full" disabled={loading} onClick={() => void load()}>
          {t("admin.refresh")}
        </Button>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">{t("admin.loginRequired")}</p>

      {error ? <p className="mt-6 text-sm text-destructive">{error}</p> : null}

      {!rows.length && !loading && authenticated && !error ? (
        <p className="mt-8 text-sm text-muted-foreground">{t("admin.empty")}</p>
      ) : null}

      {rows.length ? (
        <ul className="mt-8 space-y-3">
          {rows.map((row) => (
            <li key={row.id} className="rounded-xl border border-border/70 bg-card p-4 text-sm shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold">{row.full_name}</span>
                <span className="text-xs text-muted-foreground">
                  #{row.id} · {row.created_at ? new Date(row.created_at).toLocaleString() : "—"}
                </span>
              </div>
              <p className="mt-1 text-muted-foreground">{row.contact_method}</p>
              <p className="mt-2 whitespace-pre-wrap">{row.message}</p>
              <p className="mt-2 text-xs text-muted-foreground">
                {t("admin.emailSent")}: {row.email_sent ? "✓" : "—"}
              </p>
            </li>
          ))}
        </ul>
      ) : null}
    </main>
  );
}
