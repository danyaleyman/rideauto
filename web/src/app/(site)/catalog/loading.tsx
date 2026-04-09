export default function CatalogLoading() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-gradient-to-b from-muted/40 via-background to-background pb-10 pt-2 sm:pt-4">
      <div className="relative mx-auto min-w-0 max-w-[1440px] px-3 sm:px-6 lg:px-10">
        <div className="mb-5 min-h-11 rounded-2xl border border-border/50 bg-card/70 shadow-sm sm:mb-6 sm:rounded-3xl" />
        <div className="flex min-w-0 flex-col gap-6 lg:flex-row lg:gap-8">
          <aside className="w-full min-w-0 shrink-0 space-y-3 lg:w-80">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-28 rounded-2xl border border-border/60 bg-muted/30 ring-1 ring-black/[0.03] dark:ring-white/[0.06] sm:h-32 sm:rounded-3xl"
              />
            ))}
          </aside>
          <div className="min-w-0 flex-1">
            <div className="mb-5 h-36 rounded-2xl border border-border/50 bg-card/70 sm:rounded-3xl" />
            <ul className="flex flex-col gap-3">
              {Array.from({ length: 8 }).map((_, i) => (
                <li
                  key={i}
                  className="overflow-hidden rounded-2xl border border-border/60 bg-card/50 shadow-sm ring-1 ring-black/[0.03] dark:ring-white/[0.06] sm:rounded-3xl"
                >
                  <div className="flex flex-col sm:flex-row">
                    <div className="aspect-[16/10] bg-muted/50 sm:aspect-auto sm:h-36 sm:w-56" />
                    <div className="min-w-0 flex-1 space-y-2 p-4">
                      <div className="h-4 w-[92%] max-w-full rounded-md bg-muted/60" />
                      <div className="h-3 w-1/2 rounded-md bg-muted/50" />
                      <div className="h-6 w-28 rounded-md bg-muted/60" />
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
