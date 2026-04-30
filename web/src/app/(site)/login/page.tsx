"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { MotionFadeUp } from "@/components/ui/motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";

export default function LoginPage() {
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
            На главную
          </Link>
        </Button>
      </MotionFadeUp>
      <MotionFadeUp delay={0.05}>
        <Card className="shadow-md ring-1 ring-border/60">
          <CardHeader>
            <CardTitle className="font-heading text-xl">Вход</CardTitle>
            <CardDescription>
              Введите email — отправим одноразовую ссылку для входа.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              disabled={sending}
            />
            <label className="flex items-start gap-2 text-xs text-muted-foreground">
              <Checkbox
                checked={pdAgree}
                onCheckedChange={(v) => setPdAgree(v === true)}
                className="mt-0.5"
                aria-label="Согласие на обработку персональных данных"
              />
              <span>
                Даю согласие на обработку персональных данных по{" "}
                <Link href="/privacy" className="underline underline-offset-4 hover:text-foreground">
                  Политике конфиденциальности
                </Link>
                .
              </span>
            </label>
            <Button className="w-full rounded-full" onClick={submit} disabled={sending || !email.trim() || !pdAgree}>
              {sending ? "Отправляем..." : "Отправить ссылку"}
            </Button>
            {status === "ok" ? (
              <p className="text-sm text-emerald-600">
                Ссылка отправлена. Проверьте почту и откройте письмо.
              </p>
            ) : null}
            {status === "err" ? (
              <p className="text-sm text-destructive">
                Не удалось отправить ссылку. Попробуйте позже.
              </p>
            ) : null}
          </CardContent>
        </Card>
      </MotionFadeUp>
    </div>
  );
}
