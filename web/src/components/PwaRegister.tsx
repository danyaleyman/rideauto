"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { useLocaleContext } from "@/components/LocaleProvider";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

export function PwaRegister() {
  const { t } = useLocaleContext();
  const [installEvt, setInstallEvt] = useState<BeforeInstallPromptEvent | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !("serviceWorker" in navigator)) return;
    void navigator.serviceWorker.register("/sw.js").catch(() => {});
  }, []);

  useEffect(() => {
    const onBip = (e: Event) => {
      e.preventDefault();
      setInstallEvt(e as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", onBip);
    return () => window.removeEventListener("beforeinstallprompt", onBip);
  }, []);

  if (!installEvt || dismissed) return null;

  return (
    <div className="fixed bottom-20 end-4 z-40 max-w-xs rounded-2xl border border-border/80 bg-card p-3 shadow-lg sm:bottom-6">
      <p className="text-sm font-medium">{t("pwa.install")}</p>
      <p className="mt-1 text-xs text-muted-foreground">{t("pwa.installHint")}</p>
      <div className="mt-3 flex gap-2">
        <Button
          size="sm"
          className="rounded-full"
          onClick={() => {
            void installEvt.prompt().then(() => setDismissed(true));
          }}
        >
          {t("pwa.install")}
        </Button>
        <Button size="sm" variant="ghost" className="rounded-full" onClick={() => setDismissed(true)}>
          OK
        </Button>
      </div>
    </div>
  );
}
