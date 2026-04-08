import Link from "next/link";
import { Suspense, type ReactNode } from "react";
import { SiteFooter } from "@/components/SiteFooter";
import { MarketSwitcher } from "@/components/site/MarketSwitcher";

export function SiteShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Suspense
        fallback={<div className="h-11 border-b border-border bg-muted/40" aria-hidden />}
      >
        <MarketSwitcher />
      </Suspense>
      <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-4 py-3">
          <Link href="/" className="text-lg font-semibold tracking-tight">
            World Ride Auto
          </Link>
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
        </div>
      </header>
      <main>{children}</main>
      <SiteFooter />
    </div>
  );
}
