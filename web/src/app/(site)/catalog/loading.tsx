export default function CatalogLoading() {
  return (
    <div className="min-h-screen overflow-x-clip bg-background pb-12 pt-3 sm:pt-5">
      <div className="relative mx-auto min-w-0 max-w-[1440px] px-3 sm:px-6 lg:px-10">
        <div className="mb-4 hidden h-5 w-40 rounded-md bg-muted/60 sm:mb-5 sm:block" />
        <div className="flex min-w-0 flex-col gap-6 lg:flex-row lg:items-start lg:gap-10 xl:gap-12">
          <aside className="hidden w-full min-w-0 shrink-0 lg:block lg:w-[17.5rem] xl:w-[18.5rem]">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="space-y-2.5 border-t border-border py-4 first:border-t-0 first:pt-0">
                <div className="h-4 w-1/2 rounded-md bg-muted/60" />
                <div className="h-10 rounded-lg bg-muted/40" />
                <div className="h-10 rounded-lg bg-muted/40" />
              </div>
            ))}
          </aside>
          <div className="min-w-0 flex-1">
            <div className="mb-4 h-7 w-64 max-w-full rounded-md bg-muted/60 sm:mb-5 sm:h-8" />
            <div className="mb-4 h-10 rounded-lg bg-muted/40" />
            <ul className="flex flex-col gap-3">
              {Array.from({ length: 8 }).map((_, i) => (
                <li key={i} className="overflow-hidden rounded-xl border border-border bg-card">
                  <div className="flex flex-col md:flex-row">
                    <div className="aspect-[16/10] bg-muted/50 md:aspect-auto md:h-40 md:w-64" />
                    <div className="min-w-0 flex-1 space-y-2 p-4 md:p-5">
                      <div className="h-4 w-[70%] max-w-full rounded-md bg-muted/60" />
                      <div className="h-3 w-1/2 rounded-md bg-muted/50" />
                      <div className="h-6 w-28 rounded-md bg-muted/60 md:mt-8" />
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
