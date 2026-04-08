import Image from "next/image";
import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { fetchCar, fetchSimilar } from "@/lib/api";
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
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(n);
}

function imageUrls(raw: Record<string, unknown>): string[] {
  const d = pickCarData(raw);
  let imgs: unknown = d.images;
  if (typeof imgs === "string") {
    try {
      imgs = JSON.parse(imgs);
    } catch {
      return [];
    }
  }
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
  const similarPayload = await fetchSimilar(carId, 8, { revalidate: 60 }).catch(() => ({ result: [] }));
  const similar = (similarPayload.result || []) as SlimCar[];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <nav className="mb-6 text-sm">
        <Link href="/catalog" className="text-blue-600">
          Back to catalog
        </Link>
      </nav>

      <section className="rounded-2xl border border-zinc-200 bg-white p-6 ">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">{title}</h1>
        <p className="mt-1 text-sm text-zinc-500">ID: {carId}</p>
        <p className="mt-3 text-xl font-semibold text-zinc-900">{formatPrice(d.my_price ?? d.price)}</p>
        {typeof d.dongchedi_msrp_rub === "number" && d.dongchedi_msrp_rub > 0 ? (
          <p className="mt-1 text-sm text-zinc-600">
            Ориентир новой (КНР, MSRP): {formatPrice(d.dongchedi_msrp_rub)}
          </p>
        ) : null}
        {typeof d.dongchedi_usedcar_url === "string" && d.dongchedi_usedcar_url.trim() ? (
          <a
            href={d.dongchedi_usedcar_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 inline-block text-sm text-blue-600"
          >
            Карточка на Dongchedi
          </a>
        ) : typeof d.url === "string" && d.url.trim() ? (
          <a
            href={d.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 inline-block text-sm text-blue-600"
          >
            Original listing
          </a>
        ) : null}
        {typeof d.dongchedi_specs_url === "string" && d.dongchedi_specs_url.trim() ? (
          <a
            href={d.dongchedi_specs_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-block text-sm text-blue-600"
          >
            Параметры модели (Dongchedi)
          </a>
        ) : null}
      </section>

      {imgs.length ? (
        <section className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {imgs.slice(0, 18).map((src, idx) => (
            <div key={src} className="overflow-hidden rounded-xl border border-zinc-200">
              <Image
                src={src}
                alt={title}
                width={960}
                height={560}
                sizes="(min-width: 1024px) 31vw, (min-width: 640px) 47vw, 96vw"
                className="h-56 w-full object-cover"
                loading={idx < 2 ? "eager" : undefined}
                decoding="async"
              />
            </div>
          ))}
        </section>
      ) : null}

      <section className="mt-6 rounded-2xl border border-zinc-200 bg-white p-6 ">
        <h2 className="text-lg font-semibold text-zinc-900">Specs</h2>
        <dl className="mt-4 grid gap-x-8 gap-y-2 sm:grid-cols-2">
          {specs(raw).map(([k, v]) => (
            <div key={k} className="flex items-start justify-between gap-4 border-b border-zinc-200 py-2">
              <dt className="text-sm text-zinc-500">{k}</dt>
              <dd className="text-sm text-right text-zinc-900">{v}</dd>
            </div>
          ))}
        </dl>
      </section>

      {similar.length ? (
        <section className="mt-6">
          <h2 className="mb-3 text-lg font-semibold text-zinc-900">Similar cars</h2>
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {similar.map((car) => {
              let rawImgs: unknown = car.data?.images;
              if (typeof rawImgs === "string") {
                try {
                  rawImgs = JSON.parse(rawImgs);
                } catch {
                  rawImgs = undefined;
                }
              }
              const img =
                Array.isArray(rawImgs) && typeof rawImgs[0] === "string" ? rawImgs[0] : undefined;
              return (
                <li key={car.id} className="rounded-xl border border-zinc-200 bg-white p-3 ">
                  <Link href={`/car/${encodeURIComponent(car.id)}`} className="block">
                    <div className="overflow-hidden rounded-lg bg-zinc-100">
                      {img ? (
                        <Image
                          src={img}
                          alt={car.title || car.id}
                          width={640}
                          height={320}
                          sizes="(min-width: 1024px) 30vw, (min-width: 640px) 46vw, 96vw"
                          className="h-40 w-full object-cover"
                          loading="lazy"
                          decoding="async"
                        />
                      ) : (
                        <div className="flex h-40 items-center justify-center text-sm text-zinc-400">No image</div>
                      )}
                    </div>
                    <p className="mt-2 line-clamp-2 text-sm font-medium text-zinc-900">{car.title || car.id}</p>
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
