"use client";

import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { LogOut, Menu, Monitor, Moon, Sun, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useAuth } from "@/components/AuthProvider";

const FavoritesDialog = dynamic(
  () => import("@/components/FavoritesDialog").then((m) => m.FavoritesDialog),
  { ssr: false, loading: () => <span className="inline-flex h-8 w-[5.5rem] shrink-0 rounded-full bg-muted/50" aria-hidden /> },
);
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MOTION_TOKENS } from "@/components/ui/motion";
import {
  applyThemePreference,
  readThemePreference,
  type ThemePreference,
  writeThemePreference,
} from "@/lib/theme-preference";

export function SiteHeader() {
  const { authenticated, user, logout } = useAuth();
  const reduceMotion = useReducedMotion();
  const [mounted, setMounted] = useState(false);
  const [themePref, setThemePref] = useState<ThemePreference>("system");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

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

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setMobileMenuOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileMenuOpen]);

  const setTheme = useCallback((next: ThemePreference) => {
    setThemePref(next);
    writeThemePreference(next);
    applyThemePreference(next);
  }, []);

  const navLinks = (
    <>
      <Link className="text-muted-foreground transition-colors hover:text-foreground" href="/about">
        О компании
      </Link>
      <Link className="text-primary font-medium" href="/catalog">
        Каталог
      </Link>
      <Link className="text-muted-foreground transition-colors hover:text-foreground" href="/buy">
        Как купить
      </Link>
      <Link className="text-muted-foreground transition-colors hover:text-foreground" href="/contacts">
        Контакты
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
          className="rounded-full shadow-sm"
          aria-label="Тема оформления: светлая, системная или тёмная"
          aria-haspopup="menu"
          disabled={!mounted}
        >
          <Sun className="size-4 dark:hidden" aria-hidden />
          <Moon className="hidden size-4 dark:block" aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[14rem]">
        <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">Оформление</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={themePref} onValueChange={(v) => setTheme(v as ThemePreference)}>
          <DropdownMenuRadioItem value="light" className="cursor-pointer rounded-xl">
            <Sun className="size-4 opacity-70" aria-hidden />
            Светлая
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="system" className="cursor-pointer rounded-xl">
            <Monitor className="size-4 opacity-70" aria-hidden />
            Как в системе
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="dark" className="cursor-pointer rounded-xl">
            <Moon className="size-4 opacity-70" aria-hidden />
            Тёмная
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  const desktopActions = (
    <>
      {authenticated ? (
        <div className={mobileMenuOpen ? "hidden sm:block" : ""}>
          <FavoritesDialog />
        </div>
      ) : null}
      <div className="hidden sm:block">{themeMenu}</div>
      <Button variant="outline" size="sm" className="hidden rounded-full shadow-sm sm:inline-flex" asChild>
        <Link href="/contacts">Написать менеджеру</Link>
      </Button>
      {authenticated ? (
        <Button
          size="sm"
          variant="outline"
          className="hidden rounded-full shadow-sm sm:inline-flex"
          onClick={() => {
            void logout();
          }}
          aria-label={user?.email ? `Выйти из аккаунта ${user.email}` : "Выйти из аккаунта"}
        >
          Выйти
        </Button>
      ) : (
        <Button size="sm" className="hidden rounded-full shadow-sm sm:inline-flex" asChild>
          <Link href="/login">Войти</Link>
        </Button>
      )}
    </>
  );

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="mx-auto min-w-0 max-w-[1440px] px-3 py-2.5 sm:px-6 sm:py-3 lg:px-10">
        {/* Мобильная: бургер | Ride Auto по центру | Войти */}
        <div className="grid grid-cols-[auto_1fr_auto] items-center gap-2 sm:hidden">
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            className="rounded-full shadow-sm"
            aria-label={mobileMenuOpen ? "Закрыть меню" : "Открыть меню"}
            aria-expanded={mobileMenuOpen}
            aria-controls="site-mobile-nav"
            onClick={() => setMobileMenuOpen((v) => !v)}
          >
            {mobileMenuOpen ? <X className="size-4" aria-hidden /> : <Menu className="size-4" aria-hidden />}
          </Button>
          <Link href="/" className="text-center text-[0.95rem] font-semibold tracking-tight">
            Ride Auto
          </Link>
          <div className="flex items-center justify-end gap-1">
            {authenticated ? <FavoritesDialog /> : null}
            {authenticated ? (
              <Button
                type="button"
                variant="outline"
                size="icon-sm"
                className="rounded-full shadow-sm"
                onClick={() => {
                  void logout();
                }}
                aria-label={user?.email ? `Выйти из аккаунта ${user.email}` : "Выйти из аккаунта"}
              >
                <LogOut className="size-3.5" aria-hidden />
              </Button>
            ) : (
              <Button size="sm" variant="outline" className="rounded-full px-2.5 text-xs" asChild>
                <Link href="/login">Войти</Link>
              </Button>
            )}
          </div>
        </div>

        {/* Десктоп: логотип | навигация по центру | действия */}
        <div className="hidden min-h-[2.5rem] grid-cols-[1fr_auto_1fr] items-center gap-3 sm:grid">
          <Link href="/" className="justify-self-start text-lg font-semibold tracking-tight">
            World Ride Auto
          </Link>
          <nav className="justify-self-center flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-sm font-medium">
            {navLinks}
          </nav>
          <div className="justify-self-end flex flex-wrap items-center justify-end gap-x-2 gap-y-2 sm:gap-x-3">
            {desktopActions}
          </div>
        </div>

        <AnimatePresence initial={false}>
          {mobileMenuOpen ? (
            <motion.div
              id="site-mobile-nav"
              key="mobile-menu"
              initial={reduceMotion ? false : { opacity: 0, y: -10, scale: 0.985 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -8, scale: 0.985 }}
              transition={reduceMotion ? { duration: 0.01 } : { duration: 0.22, ease: MOTION_TOKENS.easeSoft }}
              className="w-full rounded-2xl border border-border/70 bg-background/95 p-3 shadow-sm sm:hidden"
              role="navigation"
              aria-label="Мобильное меню"
            >
              <motion.nav
                className="flex flex-col gap-1 text-sm font-medium"
                initial={reduceMotion ? false : "hidden"}
                animate={reduceMotion ? undefined : "show"}
                variants={{
                  hidden: {},
                  show: {
                    transition: {
                      staggerChildren: MOTION_TOKENS.stagger.staggerChildren + 0.005,
                      delayChildren: MOTION_TOKENS.stagger.delayChildren + 0.01,
                    },
                  },
                }}
              >
                <motion.div variants={{ hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0 } }}>
                  <Link
                    className="rounded-lg px-2 py-2 text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
                    href="/about"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    О компании
                  </Link>
                </motion.div>
                <motion.div variants={{ hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0 } }}>
                  <Link
                    className="rounded-lg px-2 py-2 text-primary"
                    href="/catalog"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    Каталог
                  </Link>
                </motion.div>
                <motion.div variants={{ hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0 } }}>
                  <Link
                    className="rounded-lg px-2 py-2 text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
                    href="/buy"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    Как купить
                  </Link>
                </motion.div>
                <motion.div variants={{ hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0 } }}>
                  <Link
                    className="rounded-lg px-2 py-2 text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
                    href="/contacts"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    Контакты
                  </Link>
                </motion.div>
                <motion.div variants={{ hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0 } }}>
                  <Link
                    className="rounded-lg px-2 py-2 font-medium text-primary transition-colors hover:bg-muted/60"
                    href="/contacts"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    Написать менеджеру
                  </Link>
                </motion.div>
              </motion.nav>

              <fieldset className="mt-3 rounded-xl border border-border/80 bg-muted/25 px-3 py-3">
                <legend className="px-1 text-sm font-medium text-foreground">Тема оформления</legend>
                <div className="mt-2 flex flex-col gap-2">
                  {(
                    [
                      { value: "light" as const, label: "Светлая", Icon: Sun },
                      { value: "system" as const, label: "Как в системе", Icon: Monitor },
                      { value: "dark" as const, label: "Тёмная", Icon: Moon },
                    ] as const
                  ).map(({ value, label, Icon }) => (
                    <label
                      key={value}
                      className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-muted/50"
                    >
                      <input
                        type="radio"
                        name="wra-theme-mobile"
                        value={value}
                        checked={themePref === value}
                        disabled={!mounted}
                        onChange={() => setTheme(value)}
                        className="size-4 accent-primary"
                      />
                      <Icon className="size-4 shrink-0 opacity-80" aria-hidden />
                      <span>{label}</span>
                    </label>
                  ))}
                </div>
              </fieldset>

              {!authenticated ? (
                <p className="mt-3 rounded-xl border border-border/80 bg-muted/25 px-3 py-2 text-sm text-muted-foreground">
                  Войдите, чтобы пользоваться избранным в этом браузере.
                </p>
              ) : null}
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>
    </header>
  );
}
