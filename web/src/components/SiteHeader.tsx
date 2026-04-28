"use client";

import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Menu, Moon, Sun, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { FavoritesDialog } from "@/components/FavoritesDialog";
import { Button } from "@/components/ui/button";
import { MOTION_TOKENS } from "@/components/ui/motion";
import { Switch } from "@/components/ui/switch";

export function SiteHeader() {
  const { authenticated, user, logout } = useAuth();
  const reduceMotion = useReducedMotion();
  const [mounted, setMounted] = useState(false);
  const [dark, setDark] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    setMounted(true);
    const stored = localStorage.getItem("wra-theme");
    const isDark = authenticated && stored === "dark";
    document.documentElement.classList.toggle("dark", isDark);
    setDark(isDark);
  }, [authenticated]);

  const onThemeChange = (checked: boolean) => {
    setDark(checked);
    document.documentElement.classList.toggle("dark", checked);
    localStorage.setItem("wra-theme", checked ? "dark" : "light");
  };

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="mx-auto flex min-w-0 max-w-[1440px] flex-wrap items-center justify-between gap-3 px-3 py-3 sm:px-6 lg:px-10">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          World Ride Auto
        </Link>
        <div className="flex w-full items-center justify-end gap-2 sm:w-auto sm:flex-wrap sm:gap-x-3 sm:gap-y-2 sm:gap-x-4">
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            className="rounded-full shadow-sm sm:hidden"
            aria-label={mobileMenuOpen ? "Закрыть меню" : "Открыть меню"}
            aria-expanded={mobileMenuOpen}
            onClick={() => setMobileMenuOpen((v) => !v)}
          >
            {mobileMenuOpen ? <X className="size-4" /> : <Menu className="size-4" />}
          </Button>

          <nav className="hidden flex-wrap items-center gap-x-4 gap-y-1 text-sm font-medium sm:flex">
            <Link className="text-muted-foreground transition-colors hover:text-foreground" href="/about">
              О компании
            </Link>
            <Link className="text-primary font-medium" href="/catalog?region=korea&source=encar">
              Каталог
            </Link>
            <Link className="text-muted-foreground transition-colors hover:text-foreground" href="/buy">
              Как купить
            </Link>
            <Link className="text-muted-foreground transition-colors hover:text-foreground" href="/contacts">
              Контакты
            </Link>
          </nav>

          {authenticated ? (
            <div className={mobileMenuOpen ? "hidden sm:block" : ""}>
              <FavoritesDialog />
            </div>
          ) : null}

          {authenticated ? (
            <div
              className="hidden items-center gap-2 rounded-full border border-border/80 bg-muted/25 px-2 py-1 shadow-sm sm:flex"
              title="Тёмная тема"
            >
              <Sun className="size-4 shrink-0 text-amber-500/90" aria-hidden />
              <Switch
                checked={mounted && dark}
                onCheckedChange={onThemeChange}
                disabled={!mounted}
                aria-label="Переключить тёмную тему"
                className="data-[state=checked]:border-primary"
              />
              <Moon className="size-4 shrink-0 text-sky-600/80 dark:text-sky-400" aria-hidden />
            </div>
          ) : null}

          <Button
            variant="outline"
            size="sm"
            className={mobileMenuOpen ? "hidden rounded-full shadow-sm sm:inline-flex" : "rounded-full shadow-sm"}
            asChild
          >
            <Link href="/contacts">Написать менеджеру</Link>
          </Button>
          {authenticated ? (
            <Button
              size="sm"
              variant="outline"
              className={mobileMenuOpen ? "hidden rounded-full shadow-sm sm:inline-flex" : "rounded-full shadow-sm"}
              onClick={() => {
                void logout();
              }}
              title={user?.email || "Выйти"}
            >
              Выйти
            </Button>
          ) : (
            <Button
              size="sm"
              className={mobileMenuOpen ? "hidden rounded-full shadow-sm sm:inline-flex" : "rounded-full shadow-sm"}
              asChild
            >
              <Link href="/login">Войти</Link>
            </Button>
          )}
        </div>

        <AnimatePresence initial={false}>
          {mobileMenuOpen ? (
            <motion.div
              key="mobile-menu"
              initial={reduceMotion ? false : { opacity: 0, y: -10, scale: 0.985 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -8, scale: 0.985 }}
              transition={reduceMotion ? { duration: 0.01 } : { duration: 0.22, ease: MOTION_TOKENS.easeSoft }}
              className="w-full rounded-2xl border border-border/70 bg-background/95 p-3 shadow-sm sm:hidden"
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
                    href="/catalog?region=korea&source=encar"
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
              </motion.nav>

              {authenticated ? (
                <div className="mt-3 flex items-center justify-between rounded-xl border border-border/80 bg-muted/25 px-3 py-2">
                  <span className="text-sm text-muted-foreground">Тёмная тема</span>
                  <div className="flex items-center gap-2">
                    <Sun className="size-4 shrink-0 text-amber-500/90" aria-hidden />
                    <Switch
                      checked={mounted && dark}
                      onCheckedChange={onThemeChange}
                      disabled={!mounted}
                      aria-label="Переключить тёмную тему"
                      className="data-[state=checked]:border-primary"
                    />
                    <Moon className="size-4 shrink-0 text-sky-600/80 dark:text-sky-400" aria-hidden />
                  </div>
                </div>
              ) : (
                <p className="mt-3 rounded-xl border border-border/80 bg-muted/25 px-3 py-2 text-sm text-muted-foreground">
                  Войдите, чтобы включить избранное и настройку темы.
                </p>
              )}
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>
    </header>
  );
}
