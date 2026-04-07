import Link from "next/link";
import type { ReactNode } from "react";

export function SiteShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)]">
      <header className="sticky top-0 z-40 border-b border-zinc-200/80 bg-white/90 backdrop-blur-md dark:border-zinc-800/80 dark:bg-zinc-950/90">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3">
          <Link href="/" className="text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
            Prod Encar
          </Link>
          <nav className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm font-medium">
            <Link className="text-blue-600 hover:underline dark:text-blue-400" href="/catalog">
              Каталог
            </Link>
            {/* Статика из папки frontend/ на том же origin (nginx). */}
            <a
              className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
              href="/howtobuy.html"
            >
              Как купить
            </a>
            <a
              className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
              href="/contacts.html"
            >
              Контакты
            </a>
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
            <a
              className="text-zinc-500 hover:text-zinc-800 dark:text-zinc-500 dark:hover:text-zinc-200"
              href="/index.html"
            >
              Классический сайт
            </a>
          </nav>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}
