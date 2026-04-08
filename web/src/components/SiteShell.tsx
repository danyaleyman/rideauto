import Link from "next/link";
import type { ReactNode } from "react";
import { SiteFooter } from "@/components/SiteFooter";

export function SiteShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)]">
      <header className="sticky top-0 z-30 border-b border-zinc-200/90 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3">
          <Link href="/" className="text-lg font-semibold tracking-tight text-zinc-900">
            World Ride Auto
          </Link>
          <nav className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm font-medium">
            <Link className="text-zinc-700 hover:text-zinc-900" href="/about">
              О компании
            </Link>
            <Link className="text-blue-700" href="/catalog">
              Каталог
            </Link>
            <Link className="text-zinc-700 hover:text-zinc-900" href="/buy">
              Как купить
            </Link>
            <Link className="text-zinc-700 hover:text-zinc-900" href="/contacts">
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
