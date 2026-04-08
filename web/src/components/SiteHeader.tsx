"use client";

import Link from "next/link";
import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { FavoritesDialog } from "@/components/FavoritesDialog";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";

export function SiteHeader() {
  const [mounted, setMounted] = useState(false);
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setMounted(true);
    const stored = localStorage.getItem("wra-theme");
    const isDark = stored === "dark";
    document.documentElement.classList.toggle("dark", isDark);
    setDark(isDark);
  }, []);

  const onThemeChange = (checked: boolean) => {
    setDark(checked);
    document.documentElement.classList.toggle("dark", checked);
    localStorage.setItem("wra-theme", checked ? "dark" : "light");
  };

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3 px-4 py-3">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          World Ride Auto
        </Link>
        <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-2 sm:gap-x-4">
          <nav className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm font-medium">
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

          <FavoritesDialog />

          <div
            className="flex items-center gap-2 rounded-full border border-border/80 bg-muted/25 px-2 py-1 shadow-sm"
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

          <Button variant="outline" size="sm" className="rounded-full shadow-sm" asChild>
            <Link href="/contacts">Написать менеджеру</Link>
          </Button>
          <Button size="sm" className="rounded-full shadow-sm" asChild>
            <Link href="/login">Войти</Link>
          </Button>
        </div>
      </div>
    </header>
  );
}
