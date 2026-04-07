import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { fetchCar } from "@/lib/api";

type PageProps = {
  params: Promise<{ ref: string }>;
};

function pickData(raw: Record<string, unknown>): Record<string, unknown> {
  const inner = raw.data;
  if (inner && typeof inner === "object" && !Array.isArray(inner)) {
    return inner as Record<string, unknown>;
  }
  return raw;
}

function carHeading(raw: Record<string, unknown>): string {
  const d = pickData(raw);
  const parts = [d.mark, d.model, d.generation ?? d.configuration]
    .filter((x): x is string => typeof x === "string" && x.length > 0);
  if (parts.length) return parts.join(" ");
  return typeof raw.title === "string" ? raw.title : "Автомобиль";
}

function numPrice(raw: Record<string, unknown>): number | undefined {
  const d = pickData(raw);
  const v = d.my_price;
  if (typeof v === "number" && !Number.isNaN(v)) return v;
  if (typeof v === "string") {
    const n = Number(v.replace(/\s/g, ""));
    if (!Number.isNaN(n)) return n;
  }
  return undefined;
}

function imageUrls(raw: Record<string, unknown>): string[] {
  const d = pickData(raw);
  const imgs = d.images;
  if (!Array.isArray(imgs)) return [];
  return imgs.filter((x): x is string => typeof x === "string" && x.length > 0);
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { ref } = await params;
  try {
    const { result } = await fetchCar(ref, { revalidate: 120 });
    if (!result || Object.keys(result).length === 0) {
      return { title: "Не найдено" };
    }
    const h = carHeading(result);
    return { title: h };
  } catch {
    return { title: "Карточка" };
  }
}

export default async function CarPage({ params }: PageProps) {
  const { ref } = await params;
  let result: Record<string, unknown>;
  try {
    const body = await fetchCar(ref, { revalidate: 60 });
    result = body.result;
  } catch {
    notFound();
  }
  if (!result || Object.keys(result).length === 0) {
    notFound();
  }

  const id =
    typeof result.id === "string"
      ? result.id
      : typeof result.car_id === "string"
        ? result.car_id
        : ref;
  const heading = carHeading(result);
  const price = numPrice(result);
  const imgs = imageUrls(result);

  return (
    <div className="mx-auto min-h-screen max-w-4xl px-4 py-8">
      <nav className="mb-6">
        <Link
          href="/catalog"
          className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
        >
          ← В каталог
        </Link>
      </nav>

      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          {heading}
        </h1>
        <p className="mt-1 text-sm text-zinc-500">id: {id}</p>
        {price != null ? (
          <p className="mt-3 text-xl font-semibold">
            {new Intl.NumberFormat("ru-RU", {
              style: "currency",
              currency: "RUB",
              maximumFractionDigits: 0,
            }).format(price)}
          </p>
        ) : null}
      </header>

      {imgs.length ? (
        <ul className="grid gap-3 sm:grid-cols-2">
          {imgs.slice(0, 12).map((src) => (
            <li key={src} className="overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-800">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={src} alt="" className="h-auto w-full object-cover" loading="lazy" />
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-zinc-500">Нет изображений в карточке.</p>
      )}

      <section className="mt-10 rounded-xl border border-zinc-200 bg-zinc-50 p-4 text-xs text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-400">
        <p>
          Полные данные приходят из PostgreSQL через{" "}
          <code className="rounded bg-zinc-200 px-1 dark:bg-zinc-800">GET /api/car/&lt;ref&gt;</code>
          ; список каталога — Meilisearch + гидратация.
        </p>
      </section>
    </div>
  );
}
