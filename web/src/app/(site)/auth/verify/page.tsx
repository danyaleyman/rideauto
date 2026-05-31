"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useLocaleContext } from "@/components/LocaleProvider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

function AuthVerifyInner() {
  const { t } = useLocaleContext();
  const router = useRouter();
  const sp = useSearchParams();
  const { verifyMagicLink } = useAuth();
  const [state, setState] = useState<"checking" | "ok" | "err">("checking");

  useEffect(() => {
    const token = (sp.get("token") || "").trim();
    if (!token) {
      setState("err");
      return;
    }
    void verifyMagicLink(token)
      .then(() => {
        setState("ok");
        window.setTimeout(() => router.replace("/catalog"), 700);
      })
      .catch(() => setState("err"));
  }, [router, sp, verifyMagicLink]);

  return (
    <Card className="shadow-md ring-1 ring-border/60">
      <CardHeader>
        <CardTitle className="font-heading text-xl">{t("auth.verifyTitle")}</CardTitle>
        <CardDescription>{t("auth.verifyDesc")}</CardDescription>
      </CardHeader>
      <CardContent>
        {state === "checking" ? <p className="text-sm text-muted-foreground">{t("auth.verifyWait")}</p> : null}
        {state === "ok" ? <p className="text-sm text-emerald-600">{t("auth.verifyOk")}</p> : null}
        {state === "err" ? (
          <div className="space-y-3">
            <p className="text-sm text-destructive">{t("auth.verifyFail")}</p>
            <Button asChild className="w-full rounded-full">
              <Link href="/login">{t("auth.verifyRetry")}</Link>
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function AuthVerifyFallback() {
  const { t } = useLocaleContext();
  return (
    <Card className="shadow-md ring-1 ring-border/60">
      <CardHeader>
        <CardTitle className="font-heading text-xl">{t("auth.verifyTitle")}</CardTitle>
        <CardDescription>{t("auth.verifyDesc")}</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">{t("auth.verifyWait")}</p>
      </CardContent>
    </Card>
  );
}

export default function AuthVerifyPage() {
  return (
    <div className="mx-auto max-w-md px-4 py-16">
      <Suspense fallback={<AuthVerifyFallback />}>
        <AuthVerifyInner />
      </Suspense>
    </div>
  );
}
