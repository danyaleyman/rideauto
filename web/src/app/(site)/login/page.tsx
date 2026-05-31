"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { useLocaleContext } from "@/components/LocaleProvider";
import { MotionFadeUp } from "@/components/ui/motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";

export default function LoginPage() {
  const { t } = useLocaleContext();
  const { requestMagicLink } = useAuth();
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState<"idle" | "ok" | "err">("idle");
  const [pdAgree, setPdAgree] = useState(false);

  const submit = async () => {
    const normalized = email.trim();
    if (!normalized) return;
    setSending(true);
    setStatus("idle");
    try {
      await requestMagicLink(normalized);
      setStatus("ok");
    } catch {
      setStatus("err");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="mx-auto max-w-md px-4 py-16">
      <MotionFadeUp>
        <Button variant="ghost" size="sm" className="mb-6 -ms-1 gap-1 ps-2 text-muted-foreground" asChild>
          <Link href="/">
            <ArrowLeft className="size-4" />
            {t("login.backHome")}
          </Link>
        </Button>
      </MotionFadeUp>
      <MotionFadeUp delay={0.05}>
        <Card className="shadow-md ring-1 ring-border/60">
          <CardHeader>
            <CardTitle className="font-heading text-xl">{t("login.title")}</CardTitle>
            <CardDescription>{t("login.hint")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              aria-label={t("login.email")}
              disabled={sending}
            />
            <label className="flex items-start gap-2 text-xs text-muted-foreground">
              <Checkbox
                checked={pdAgree}
                onCheckedChange={(v) => setPdAgree(v === true)}
                className="mt-0.5"
                aria-label={t("buy.pdAgree")}
              />
              <span>
                {t("buy.pdAgree")}{" "}
                <Link href="/privacy" className="underline underline-offset-4 hover:text-foreground">
                  {t("buy.privacyLink")}
                </Link>
                .
              </span>
            </label>
            <Button className="w-full rounded-full" onClick={submit} disabled={sending || !email.trim() || !pdAgree}>
              {sending ? t("login.sending") : t("login.submit")}
            </Button>
            {status === "ok" ? <p className="text-sm text-emerald-600">{t("login.success")}</p> : null}
            {status === "err" ? <p className="text-sm text-destructive">{t("login.error")}</p> : null}
          </CardContent>
        </Card>
      </MotionFadeUp>
    </div>
  );
}
