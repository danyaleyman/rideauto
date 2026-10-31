"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, Car, LogOut, Monitor, Moon, Phone, Sun, UserRound } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useAuth } from "@/components/AuthProvider";
import { useLocaleContext } from "@/components/LocaleProvider";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";

const FavoritesDialog = dynamic(
  () => import("@/components/FavoritesDialog").then((m) => m.FavoritesDialog),
  { ssr: false, loading: () => <span className="inline-flex h-8 w-[5.5rem] shrink-0 rounded-full bg-muted/50" aria-hidden /> },
);
const CompareLinkButton = dynamic(
  () => import("@/components/catalog/CompareLinkButton").then((m) => m.CompareLinkButton),
  { ssr: false, loading: () => null },
);
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { siteHeaderSafeTopClass } from "@/lib/design-system";
import { cn } from "@/lib/utils";
import {
  applyThemePreference,
  readThemePreference,
  type ThemePreference,
  writeThemePreference,
} from "@/lib/theme-preference";

type MobileTab = { href: string; labelKey: string; Icon: typeof Car };

const MOBILE_TABS: MobileTab[] = [
  { href: "/catalog", labelKey: "header.catalog", Icon: Car },
  { href: "/buy",     labelKey: "header.buy",     Icon: BookOpen },
  { href: "/contacts",labelKey: "header.contacts", Icon: Phone },
];


export function SiteHeader() {
  const { authenticated, user, logout } = useAuth();
  const { t } = useLocaleContext();
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);
  const [themePref, setThemePref] = useState<ThemePreference>("system");

  useEffect(() => {
    setMounted(true);
    const initial = readThemePreference();
    setThemePref(initial);
    applyThemePreference(initial);
  }, []);

  useEffect(() => {
    if (!mounted || themePref !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyThemePreference("system");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [mounted, themePref]);

  const setTheme = useCallback((next: ThemePreference) => {
    setThemePref(next);
    writeThemePreference(next);
    applyThemePreference(next);
  }, []);

  const navLinks = (
    <>
      <Link className="text-muted-foreground transition-colors hover:text-foreground" href="/#company">
        {t("header.about")}
      </Link>
      <Link className="text-primary font-medium" href="/catalog">
        {t("header.catalog")}
      </Link>
      <Link className="text-muted-foreground transition-colors hover:text-foreground" href="/buy">
        {t("header.buy")}
      </Link>
      <Link className="text-muted-foreground transition-colors hover:text-foreground" href="/contacts">
        {t("header.contacts")}
      </Link>
    </>
  );

  const themeMenu = (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="icon-sm"
          className="rounded-full"
          aria-label={t("header.theme")}
          aria-haspopup="menu"
          disabled={!mounted}
        >
          <Sun className="size-4 dark:hidden" aria-hidden />
          <Moon className="hidden size-4 dark:block" aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[14rem]">
        <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">{t("header.themeLabel")}</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={themePref} onValueChange={(v) => setTheme(v as ThemePreference)}>
          <DropdownMenuRadioItem value="light" className="cursor-pointer rounded-xl">
            <Sun className="size-4 opacity-70" aria-hidden />
            {t("header.themeLight")}
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="system" className="cursor-pointer rounded-xl">
            <Monitor className="size-4 opacity-70" aria-hidden />
            {t("header.themeSystem")}
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="dark" className="cursor-pointer rounded-xl">
            <Moon className="size-4 opacity-70" aria-hidden />
            {t("header.themeDark")}
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  const showCompare = authenticated;

  const accountMenu =
    authenticated ? (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="hidden max-w-[11rem] shrink-0 rounded-full sm:inline-flex"
            aria-label={t("header.account")}
          >
            <UserRound className="size-4 shrink-0 opacity-80" aria-hidden />
            <span className="truncate">{user?.email?.split("@")[0] ?? t("header.account")}</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-[12rem]">
          {user?.email ? (
            <>
              <DropdownMenuLabel className="truncate text-xs font-normal text-muted-foreground">
                {user.email}
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
            </>
          ) : null}
          <DropdownMenuItem asChild className="cursor-pointer rounded-xl">
            <Link href="/account">{t("header.account")}</Link>
          </DropdownMenuItem>
          <DropdownMenuItem
            className="cursor-pointer rounded-xl text-destructive focus:text-destructive"
            onSelect={(e) => {
              e.preventDefault();
              void logout();
            }}
          >
            <LogOut className="size-4 opacity-70" aria-hidden />
            {t("header.logout")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    ) : (
      <Button size="sm" className="hidden shrink-0 rounded-full sm:inline-flex" asChild>
        <Link href="/login">{t("header.login")}</Link>
      </Button>
    );

  const desktopActions = (
    <>
      {showCompare ? <CompareLinkButton className="hidden shrink-0 rounded-full sm:inline-flex" /> : null}
      <LocaleSwitcher className="hidden shrink-0 sm:inline-flex" />
      {authenticated ? (
        <div className="shrink-0">
          <FavoritesDialog />
        </div>
      ) : null}
      <div className="hidden shrink-0 sm:block">{themeMenu}</div>
      <Button
        variant="outline"
        size="sm"
        className="hidden shrink-0 rounded-full sm:inline-flex"
        asChild
      >
        <Link href="/contacts">{t("header.manager")}</Link>
      </Button>
      {accountMenu}
    </>
  );

  return (
    <>
      <header
        className={`sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 ${siteHeaderSafeTopClass}`}
      >
        <div className="mx-auto flex min-h-14 min-w-0 max-w-[1440px] items-center px-3 py-2 sm:min-h-16 sm:px-6 sm:py-3 lg:px-10">
          {/* Мобильная: логотип слева | иконки справа */}
          <div className="flex w-full min-w-0 items-center justify-between gap-2 sm:hidden">
            <Link href="/" className="text-[0.95rem] font-semibold tracking-tight">
              Ride Auto
            </Link>
            <div className="flex items-center gap-1">
              {showCompare ? <CompareLinkButton className="rounded-full px-2" /> : null}
              {authenticated ? <FavoritesDialog /> : null}
              {themeMenu}
            </div>
          </div>

          {/* Десктоп: логотип | навигация по центру | действия */}
          <div className="hidden w-full min-h-[2.5rem] grid-cols-[1fr_auto_1fr] items-center gap-3 sm:grid">
            <Link href="/" className="justify-self-start text-lg font-semibold tracking-tight">
              Ride Auto
            </Link>
            <nav
              className="justify-self-center flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-sm font-medium"
              aria-label={t("header.navAria")}
            >
              {navLinks}
            </nav>
            <div className="justify-self-end flex max-w-[min(100%,42rem)] flex-nowrap items-center justify-end gap-2 overflow-x-auto overflow-y-hidden sm:gap-2.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              {desktopActions}
            </div>
          </div>
        </div>
      </header>

      {/* Мобильный bottom tab bar */}
      <nav
        className={cn(
          "fixed inset-x-0 bottom-0 z-40 sm:hidden",
          "border-t border-border bg-background/97 backdrop-blur-xl",
          "pb-[env(safe-area-inset-bottom)]",
        )}
        aria-label={t("header.mobileNavAria")}
      >
        <div className="flex items-stretch">
          {MOBILE_TABS.map((tab) => {
            const Icon = tab.Icon;
            const active = pathname === tab.href || (tab.href !== "/" && (pathname?.startsWith(tab.href + "/") ?? false));
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={cn(
                  "flex flex-1 flex-col items-center justify-center gap-0.5 py-2.5 text-[10px] font-medium transition-colors min-h-[3.25rem]",
                  active ? "text-primary" : "text-muted-foreground hover:text-foreground",
                )}
                aria-current={active ? "page" : undefined}
              >
                <Icon
                  className={cn("size-5 transition-transform", active && "scale-110")}
                  aria-hidden
                  strokeWidth={active ? 2.5 : 1.75}
                />
                <span>{t(tab.labelKey as Parameters<typeof t>[0])}</span>
              </Link>
            );
          })}
          {authenticated ? (
            <Link
              href="/account"
              className={cn(
                "flex flex-1 flex-col items-center justify-center gap-0.5 py-2.5 text-[10px] font-medium transition-colors min-h-[3.25rem]",
                pathname === "/account" ? "text-primary" : "text-muted-foreground hover:text-foreground",
              )}
              aria-current={pathname === "/account" ? "page" : undefined}
            >
              <UserRound
                className={cn("size-5 transition-transform", pathname === "/account" && "scale-110")}
                aria-hidden
                strokeWidth={pathname === "/account" ? 2.5 : 1.75}
              />
              <span>{t("header.account")}</span>
            </Link>
          ) : (
            <Link
              href="/login"
              className="flex flex-1 flex-col items-center justify-center gap-0.5 py-2.5 text-[10px] font-medium text-muted-foreground hover:text-foreground transition-colors min-h-[3.25rem]"
            >
              <UserRound className="size-5" aria-hidden strokeWidth={1.75} />
              <span>{t("header.login")}</span>
            </Link>
          )}
        </div>
      </nav>
    </>
  );
}
