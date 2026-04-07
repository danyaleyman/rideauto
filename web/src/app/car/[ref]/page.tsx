import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { fetchCar, fetchSearch } from "@/lib/api";
import { buildCarMetadata, carHeading, pickCarData } from "@/lib/car-seo";
import type { SlimCar } from "@/lib/types";

type PageProps = { params: Promise<{ ref: string }> };

function asPrice(v: unknown): number | null {
  if (typeof v === "number" && !Number.isNaN(v)) return v;
  if (typeof v === "string") {
    const n = Number(v.replace(/\s/g, ""));
    return Number.isNaN(n) ? null : n;
  }
  return null;
}

function formatPrice(v: unknown): string {
  const n = asPrice(v);
  if (n == null) return "Price on request";
  return new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 }).format(n);
}

function imageUrls(raw: Record<string, unknown>): string[] {
  const d = pickCarData(raw);
  const imgs = d.images;
  if (!Array.isArray(imgs)) return [];
  return imgs.filter((x): x is string => typeof x === "string" && x.length > 0);
}

function text(v: unknown): string | null {
  if (v == null) return null;
  const s = String(v).trim();
  return s.length ? s : null;
}

function specs(raw: Record<string, unknown>): Array<[string, string]> {
  const d = pickCarData(raw);
  const rows: Array<[string, string | null]> = [
    ["Make", text(d.mark)],
    ["Model", text(d.model)],
    ["Generation", text(d.generation ?? d.configuration)],
    ["Year", text(d.year)],
    ["Mileage", text(d.km_age) ? `${d.km_age} km` : null],
    ["Engine", text(d.engine_type)],
    ["Displacement", text(d.engine_displacement_cc) ? `${d.engine_displacement_cc} cc` : null],
    ["Transmission", text(d.transmission_type)],
    ["Drive", text(d.drive_type ?? d.prep_drive_type)],
    ["Body", text(d.body_type)],
    ["Color", text(d.color)],
    ["VIN / Number", text(d.vehicle_no ?? d.vin)],
  ];
  return rows.filter((x): x is [string, string] => Boolean(x[1]));
}

async function fetchSimilar(raw: Record<string, unknown>, selfId: string): Promise<SlimCar[]> {
  const d = pickCarData(raw);
  const mark = typeof d.mark === "string" ? d.mark : undefined;
  const model = typeof d.model === "string" ? d.model : undefined;
  if (!mark) return [];
  try {
    const body = await fetchSearch({ mark, model, per_page: "8", sort: "date_new" }, { revalidate: 60 });
    return body.result.filter((x) => String(x.id) !== String(selfId)).slice(0, 6);
  } catch {
    return [];
  }
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { ref } = await params;
  try {
    const { result } = await fetchCar(ref, { revalidate: 120 });
    if (!result || Object.keys(result).length === 0) return { title: "Not found" };
    return buildCarMetadata(ref, result);
  } catch {
    return { title: "Car" };
  }
}

export default async function CarPage({ params }: PageProps) {
  const { ref } = await params;
  const body = await fetchCar(ref, { revalidate: 60 });
  const raw = body.result;
  if (!raw || Object.keys(raw).length === 0) notFound();

  const d = pickCarData(raw);
  const title = carHeading(raw);
  const imgs = imageUrls(raw);
  const carId = typeof raw.id === "string" ? raw.id : ref;
  const similar = await fetchSimilar(raw, carId);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <nav className="mb-6 text-sm">
        <Link href="/catalog" className="text-blue-600 hover:underline dark:text-blue-400">Back to catalog</Link>
      </nav>

      <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">{title}</h1>
        <p className="mt-1 text-sm text-zinc-500">ID: {carId}</p>
        <p className="mt-3 text-xl font-semibold text-zinc-900 dark:text-zinc-50">{formatPrice(d.my_price ?? d.price)}</p>
        {typeof d.url === "string" && d.url.trim() ? (
          <a href={d.url} target="_blank" rel="noopener noreferrer" className="mt-3 inline-block text-sm text-blue-600 hover:underline dark:text-blue-400">Original listing</a>
        ) : null}
      </section>

      {imgs.length ? (
        <section className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {imgs.slice(0, 18).map((src) => (
            <div key={src} className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={src} alt={title} className="h-56 w-full object-cover" loading="lazy" />
            </div>
          ))}
        </section>
      ) : null}

      <section className="mt-6 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Specs</h2>
        <dl className="mt-4 grid gap-x-8 gap-y-2 sm:grid-cols-2">
          {specs(raw).map(([k, v]) => (
            <div key={k} className="flex items-start justify-between gap-4 border-b border-zinc-200 py-2 dark:border-zinc-800">
              <dt className="text-sm text-zinc-500">{k}</dt>
              <dd className="text-sm text-right text-zinc-900 dark:text-zinc-100">{v}</dd>
            </div>
          ))}
        </dl>
      </section>

      {similar.length ? (
        <section className="mt-6">
          <h2 className="mb-3 text-lg font-semibold text-zinc-900 dark:text-zinc-50">Similar cars</h2>
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {similar.map((car) => {
              const img = Array.isArray(car.data?.images) ? car.data.images?.[0] : undefined;
              return (
                <li key={car.id} className="rounded-xl border border-zinc-200 bg-white p-3 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
                  <Link href={`/car/${encodeURIComponent(car.id)}`} className="block">
                    <div className="overflow-hidden rounded-lg bg-zinc-100 dark:bg-zinc-900">
                      {img ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={img} alt={car.title || car.id} className="h-40 w-full object-cover" loading="lazy" />
                      ) : (
                        <div className="flex h-40 items-center justify-center text-sm text-zinc-400">No image</div>
                      )}
                    </div>
                    <p className="mt-2 line-clamp-2 text-sm font-medium text-zinc-900 dark:text-zinc-100">{car.title || car.id}</p>
                    <p className="mt-1 text-sm text-zinc-500">{formatPrice(car.price)}</p>
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
