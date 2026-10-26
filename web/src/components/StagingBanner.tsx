/** Виден только на стейджинге (NEXT_PUBLIC_NOINDEX=1 на сборке). */
export function StagingBanner() {
  if (process.env.NEXT_PUBLIC_NOINDEX !== "1") return null;
  return (
    <div className="bg-amber-500 px-3 py-1.5 text-center text-xs font-semibold text-black sm:text-sm">
      STAGING — не продакшен. Смотрим правки здесь, на rideauto.ru ещё то, что уже залито.
    </div>
  );
}
