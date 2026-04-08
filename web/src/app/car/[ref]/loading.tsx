export default function CarLoading() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 rounded border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-500">Загрузка карточки…</div>
      <section className="rounded-2xl border border-zinc-200 bg-white p-6">
        <div className="h-8 w-2/3 rounded bg-zinc-200" />
        <div className="mt-2 h-4 w-40 rounded bg-zinc-200" />
        <div className="mt-4 h-7 w-32 rounded bg-zinc-200" />
      </section>
      <section className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="h-56  rounded-xl border border-zinc-200 bg-zinc-100"
          />
        ))}
      </section>
      <section className="mt-6 rounded-2xl border border-zinc-200 bg-white p-6">
        <div className="h-6 w-24 rounded bg-zinc-200" />
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-8  rounded bg-zinc-100" />
          ))}
        </div>
      </section>
    </div>
  );
}
