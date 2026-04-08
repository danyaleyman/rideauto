import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="border-t border-zinc-200 bg-zinc-50 py-8 text-sm text-zinc-600">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <nav className="flex flex-wrap gap-x-4 gap-y-1">
          <Link href="/privacy">
            Конфиденциальность
          </Link>
          <Link href="/cookies">
            Cookie
          </Link>
          <Link href="/agreement">
            Соглашение
          </Link>
        </nav>
        <p className="text-zinc-500">© World Ride Auto 2026</p>
      </div>
    </footer>
  );
}
