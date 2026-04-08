export default function CatalogLoading() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <div className="mb-6 rounded border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-500">Загрузка каталога…</div>
      <div className="flex flex-col gap-8 lg:flex-row">
        <aside className="w-full shrink-0 space-y-3 lg:w-72">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-32  rounded-xl border border-zinc-200 bg-zinc-100"
            />
          ))}
        </aside>
        <div className="min-w-0 flex-1">
          <ul className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 12 }).map((_, i) => (
              <li
                key={i}
                className="overflow-hidden rounded-xl border border-zinc-200 bg-white"
              >
                <div className="aspect-[16/10] bg-zinc-200" />
                <div className="space-y-2 p-4">
                  <div className="h-4 w-11/12 rounded bg-zinc-200" />
                  <div className="h-3 w-1/2 rounded bg-zinc-200" />
                  <div className="h-5 w-1/3 rounded bg-zinc-200" />
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
