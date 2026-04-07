import Link from "next/link";
import type { Metadata } from "next";
import { fetchSearch } from "@/lib/api";
import type { SlimCar } from "@/lib/types";

type PageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function firstImageUrl(car: SlimCar): string | undefined {
  const imgs = car.data?.images;
  if (!Array.isArray(imgs) || !imgs.length) return undefined;
  const u = imgs[0];
  return typeof u === "string" ? u : undefined;
}

function formatPrice(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  try {
    return new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency: "RUB",
      maximumFractionDigits: 0,
    }).format(n);
  } catch {
    return `${n} ₽`;
  }
}

export async function generateMetadata({
  searchParams,
}: PageProps): Promise<Metadata> {
  const sp = await searchParams;
  const q = typeof sp.q === "string" ? sp.q.trim() : "";
  const title = q ? `Поиск: ${q}` : "Каталог";
  return {
    title,
    description:
      "Каталог автомобилей: поиск и фильтры через Meilisearch, карточки из PostgreSQL.",
  };
}

export default async function CatalogPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  let data;
  let err: string | null = null;
  try {
    data = await fetchSearch(sp, { revalidate: 30 });
  } catch (e) {
    err = e instanceof Error ? e.message : "Ошибка загрузки";
    data = { result: [], meta: { total: 0, limit: 12, per_page: 12, pages: 1, offset: 0 } };
  }

  const { result: cars, meta } = data;

  return (
    <div className="mx-auto min-h-screen max-w-6xl px-4 py-8">
      <header className="mb-8 flex flex-col gap-4 border-b border-zinc-200 pb-6 dark:border-zinc-800 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm text-zinc-500">SSR — данные с API при первом рендере</p>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
            Каталог
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Найдено: {meta.total.toLocaleString("ru-RU")}
            {meta.processing_time_ms != null
              ? ` · Meilisearch ${meta.processing_time_ms} ms`
              : ""}
          </p>
        </div>
        <Link
          href="/"
          className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
        >
          На главную
        </Link>
      </header>

      {err ? (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
          {err} — проверьте, что API запущен и заданы{" "}
          <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">WRA_API_INTERNAL</code> /{" "}
          <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">NEXT_PUBLIC_API_BASE</code>.
        </p>
      ) : null}

      <ul className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {cars.map((car) => {
          const img = firstImageUrl(car);
          return (
            <li key={car.id}>
              <Link
                href={`/car/${encodeURIComponent(car.id)}`}
                className="group block overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm transition hover:border-zinc-300 hover:shadow-md dark:border-zinc-800 dark:bg-zinc-950 dark:hover:border-zinc-600"
              >
                <div className="aspect-[16/10] bg-zinc-100 dark:bg-zinc-900">
                  {img ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={img}
                      alt=""
                      className="h-full w-full object-cover transition group-hover:scale-[1.02]"
                      loading="lazy"
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center text-sm text-zinc-400">
                      Нет фото
                    </div>
                  )}
                </div>
                <div className="space-y-1 p-4">
                  <p className="line-clamp-2 text-sm font-medium leading-snug text-zinc-900 dark:text-zinc-100">
                    {car.title || car.id}
                  </p>
                  <p className="text-xs text-zinc-500">
                    {car.year_num ? `${car.year_num} · ` : ""}
                    {car.id}
                  </p>
                  <p className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
                    {formatPrice(car.price)}
                  </p>
                </div>
              </Link>
            </li>
          );
        })}
      </ul>

      {meta.next_cursor ? (
        <nav className="mt-10 flex justify-center">
          <Link
            href={`/catalog?${nextPageQuery(sp, meta.next_cursor)}`}
            className="rounded-full border border-zinc-300 bg-white px-5 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800"
          >
            Следующая страница
          </Link>
        </nav>
      ) : null}
    </div>
  );
}

function nextPageQuery(
  sp: Record<string, string | string[] | undefined>,
  cursor: string,
): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(sp)) {
    if (v === undefined || k === "cursor") continue;
    if (Array.isArray(v)) {
      for (const x of v) usp.append(k, x);
    } else {
      usp.set(k, v);
    }
  }
  usp.set("cursor", cursor);
  if (!usp.has("per_page")) usp.set("per_page", "12");
  return usp.toString();
}
