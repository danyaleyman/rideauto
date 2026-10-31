"use client";

import { useState, useCallback } from "react";
import { Languages, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { translateTextClient } from "@/lib/client-api";
import { useLocaleContext } from "@/components/LocaleProvider";

type Props = {
  text: string;
  onTranslated: (translated: string) => void;
  isTranslated?: boolean;
  onRevert?: () => void;
  /** Целевой язык перевода. По умолчанию — из locale контекста. */
  targetLang?: string;
  className?: string;
};

/**
 * Кнопка «Перевести / Оригинал» через DeepSeek API.
 */
export function TranslateButton({ text, onTranslated, isTranslated, onRevert, targetLang, className }: Props) {
  const { t, locale } = useLocaleContext();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const resolvedTarget = targetLang ?? (locale === "en" ? "en" : "ru");

  const handleTranslate = useCallback(async () => {
    if (!text.trim()) return;
    setLoading(true);
    setError(false);
    try {
      const res = await translateTextClient(text, {
        provider: "deepseek",
        targetLang: resolvedTarget,
      });
      onTranslated(res.translated_text);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [text, resolvedTarget, onTranslated]);

  if (isTranslated) {
    return (
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className={`h-7 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground ${className ?? ""}`}
        onClick={onRevert}
      >
        <Languages className="size-3.5" aria-hidden />
        {t("car.translate.revert")}
      </Button>
    );
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      disabled={loading}
      className={`h-7 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground disabled:opacity-60 ${className ?? ""}`}
      onClick={() => void handleTranslate()}
    >
      {loading ? (
        <Loader2 className="size-3.5 animate-spin" aria-hidden />
      ) : (
        <Languages className="size-3.5" aria-hidden />
      )}
      {error ? t("car.translate.error") : t("car.translate.translate")}
    </Button>
  );
}
