import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="border-t border-zinc-200 bg-zinc-50/80 py-8 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-400">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <nav className="flex flex-wrap gap-x-4 gap-y-1">
          <Link className="hover:text-zinc-900 dark:hover:text-zinc-200" href="/privacy">
            Конфиденциальность
          </Link>
          <Link className="hover:text-zinc-900 dark:hover:text-zinc-200" href="/cookies">
            Cookie
          </Link>
          <Link className="hover:text-zinc-900 dark:hover:text-zinc-200" href="/agreement">
            Соглашение
          </Link>
        </nav>
        <p className="text-zinc-500">© World Ride Auto 2026</p>
      </div>
    </footer>
  );
}
