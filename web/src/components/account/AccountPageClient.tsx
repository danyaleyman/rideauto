"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Bookmark, GitCompareArrows, Heart, Trash2 } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { useFavorites } from "@/hooks/use-favorites";
import { useSavedCatalogSearches } from "@/hooks/use-saved-catalog-searches";
import { useCompareCars } from "@/hooks/use-compare-cars";
import { useLocaleContext } from "@/components/LocaleProvider";
import { formatPriceLabel } from "@/lib/format-price";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  hasActivePushSubscription,
  subscribeToWebPush,
  unsubscribeFromWebPush,
} from "@/lib/push-client";

export function AccountPageClient() {
  const { t } = useLocaleContext();
  const router = useRouter();
  const { authenticated, loading, user, logout } = useAuth();
  const { items: favorites, remove: removeFavorite } = useFavorites();
  const { items: saved, remove: removeSaved, setNotifyEnabled, hrefFor } = useSavedCatalogSearches();
  const { compareHref, count: compareCount, ids: compareIds, remove: removeCompare } = useCompareCars();
  const [pushOn, setPushOn] = useState(false);
  const [pushBusy, setPushBusy] = useState(false);

  useEffect(() => {
    if (!loading && !authenticated) {
      router.replace("/login?next=/account");
    }
  }, [loading, authenticated, router]);

  useEffect(() => {
    if (!authenticated) return;
    void hasActivePushSubscription().then(setPushOn);
  }, [authenticated]);

  if (loading || !authenticated) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-16 text-sm text-muted-foreground">
        {t("account.loading")}
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-10 sm:py-14">
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("account.title")}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{user?.email}</p>
        </div>
        <Button variant="outline" size="sm" className="rounded-full" onClick={() => void logout()}>
          {t("account.logout")}
        </Button>
      </div>

      <div className="flex flex-col gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t("push.title")}</CardTitle>
            <CardDescription>{t("push.hint")}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-3">
            <Switch
              id="push-enable"
              checked={pushOn}
              disabled={pushBusy}
              onCheckedChange={(v) => {
                setPushBusy(true);
                void (async () => {
                  if (v) {
                    const r = await subscribeToWebPush();
                    if (r === "ok") setPushOn(true);
                    else if (r === "denied") alert(t("push.denied"));
                    else if (r === "unsupported") alert(t("push.unsupported"));
                  } else {
                    await unsubscribeFromWebPush();
                    setPushOn(false);
                  }
                  setPushBusy(false);
                })();
              }}
            />
            <Label htmlFor="push-enable">{pushOn ? t("push.enabled") : t("push.enable")}</Label>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Heart className="size-5 opacity-70" aria-hidden />
              {t("account.favoritesTitle")}
            </CardTitle>
            <CardDescription>{t("account.favoritesHint")}</CardDescription>
          </CardHeader>
          <CardContent>
            {!favorites.length ? (
              <p className="text-sm text-muted-foreground">{t("account.favoritesEmpty")}</p>
            ) : (
              <ul className="space-y-2">
                {favorites.map((car) => (
                  <li
                    key={car.id}
                    className="flex items-start gap-2 rounded-xl border border-border/70 bg-muted/20 p-3 text-sm"
                  >
                    <div className="min-w-0 flex-1">
                      <Link
                        href={`/car/${encodeURIComponent(car.id)}`}
                        className="font-medium text-primary underline-offset-2 hover:underline"
                      >
                        {car.title}
                      </Link>
                      <p className="mt-0.5 tabular-nums text-xs text-muted-foreground">
                        {formatPriceLabel(car.price)}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-xs"
                      aria-label={t("account.removeFavorite")}
                      onClick={() => void removeFavorite(car.id)}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Bookmark className="size-5 opacity-70" aria-hidden />
              {t("account.savedTitle")}
            </CardTitle>
            <CardDescription>{t("account.savedHint")}</CardDescription>
          </CardHeader>
          <CardContent>
            {!saved.length ? (
              <p className="text-sm text-muted-foreground">{t("account.savedEmpty")}</p>
            ) : (
              <ul className="space-y-3">
                {saved.map((item) => (
                  <li
                    key={item.id}
                    className="flex flex-col gap-2 rounded-xl border border-border/70 bg-muted/20 p-3 text-sm sm:flex-row sm:items-center"
                  >
                    <Link href={hrefFor(item)} className="min-w-0 flex-1 font-medium text-primary hover:underline">
                      {item.name}
                    </Link>
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-2">
                        <Switch
                          id={`notify-${item.id}`}
                          checked={item.notifyEnabled !== false}
                          onCheckedChange={(v) => void setNotifyEnabled(item.id, v)}
                        />
                        <Label htmlFor={`notify-${item.id}`} className="text-xs text-muted-foreground">
                          {t("account.notifyEmail")}
                        </Label>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        aria-label={t("account.removeSaved")}
                        onClick={() => void removeSaved(item.id)}
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <GitCompareArrows className="size-5 opacity-70" aria-hidden />
              {t("account.compareTitle")}
            </CardTitle>
            <CardDescription>{t("account.compareHint")}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {compareCount === 0 ? (
              <p className="text-sm text-muted-foreground">{t("account.compareEmpty")}</p>
            ) : (
              <>
                <ul className="space-y-1 text-sm">
                  {compareIds.map((id) => (
                    <li key={id} className="flex items-center justify-between gap-2">
                      <span className="truncate font-mono text-xs">{id}</span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => removeCompare(id)}
                      >
                        {t("compare.remove")}
                      </Button>
                    </li>
                  ))}
                </ul>
                <Button variant="secondary" size="sm" className="w-fit rounded-full" asChild>
                  <Link href={compareHref}>{t("account.openCompare")}</Link>
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
