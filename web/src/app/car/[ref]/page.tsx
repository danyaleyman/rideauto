import Image from "next/image";
import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { fetchCar, fetchSimilar } from "@/lib/api";
import { buildCarMetadata, carHeading, pickCarData } from "@/lib/car-seo";
import { formatPriceLabel } from "@/lib/format-price";
import { getAllCarPhotoUrls } from "@/lib/car-gallery-images";
import type { SlimCar } from "@/lib/types";
import CarPhotoGallery from "@/components/car/CarPhotoGallery";
import { CarDetailAccordions } from "@/components/car/CarDetailAccordions";
import { CarPurchaseSidebar } from "@/components/car/CarPurchaseSidebar";
import { CarHeroMeta } from "@/components/car/CarHeroMeta";
import { CarTrustStrip } from "@/components/car/CarTrustStrip";
import { extractCarImageUrls } from "@/lib/car-images";
import { Button } from "@/components/ui/button";

type PageProps = { params: Promise<{ ref: string }> };

function formatSimilarPrice(v: unknown): string {
  if (v == null || v === "") return "Цена по запросу";
  if (typeof v === "number" && Number.isFinite(v)) return formatPriceLabel(v);
  if (typeof v === "string") {
    const n = Number(v.replace(/\s/g, ""));
    if (!Number.isNaN(n)) return formatPriceLabel(n);
  }
  return "Цена по запросу";
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { ref } = await params;
  try {
    const { result } = await fetchCar(ref, { revalidate: 120 });
    if (!result || Object.keys(result).length === 0) return { title: "Не найдено" };
    return buildCarMetadata(ref, result);
  } catch {
    return { title: "Автомобиль" };
  }
}

export default async function CarPage({ params }: PageProps) {
  const { ref } = await params;
  const body = await fetchCar(ref, { revalidate: 60 });
  const raw = body.result;
  if (!raw || Object.keys(raw).length === 0) notFound();

  const d = pickCarData(raw);
  const title = carHeading(raw);
  const imgs = getAllCarPhotoUrls(d as Record<string, unknown>);
  const carId = typeof raw.id === "string" ? raw.id : ref;
  const similarPayload = await fetchSimilar(carId, 8, { revalidate: 60 }).catch(() => ({ result: [] }));
  const similar = (similarPayload.result || []) as SlimCar[];

  const rubPrice =
    typeof d.my_price === "number"
      ? d.my_price
      : typeof d.my_price === "string"
        ? Number(String(d.my_price).replace(/\s/g, ""))
        : null;

  const priceWon =
    typeof d.price_won === "number" && Number.isFinite(d.price_won)
      ? d.price_won
      : typeof d.price_won === "string"
        ? Number(String(d.price_won).replace(/\s/g, ""))
        : null;

  const priceCny =
    typeof d.price_cny === "number" && Number.isFinite(d.price_cny)
      ? d.price_cny
      : typeof d.price_cny === "string"
        ? Number(String(d.price_cny).replace(/\s/g, ""))
        : null;

  const sourceUrl =
    typeof d.dongchedi_usedcar_url === "string" && d.dongchedi_usedcar_url.trim()
      ? d.dongchedi_usedcar_url.trim()
      : typeof d.url === "string" && d.url.trim()
        ? d.url.trim()
        : null;

  const extra =
    d.extra && typeof d.extra === "object" && !Array.isArray(d.extra)
      ? (d.extra as Record<string, unknown>)
      : undefined;
  const diagnosisPhotosCount = Array.isArray(extra?.diagnosis_photos) ? extra.diagnosis_photos.length : 0;

  const description =
    typeof d.description === "string" && d.description.trim() ? d.description.trim() : null;

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <nav className="mb-6 flex flex-wrap items-center gap-3 text-sm">
        <Button variant="ghost" size="sm" className="h-8 px-2" asChild>
          <Link href="/catalog">← Каталог</Link>
        </Button>
        {typeof d.dongchedi_specs_url === "string" && d.dongchedi_specs_url.trim() ? (
          <Button variant="outline" size="sm" className="h-8 rounded-full" asChild>
            <a href={d.dongchedi_specs_url} target="_blank" rel="noopener noreferrer">
              Параметры модели (Dongchedi)
            </a>
          </Button>
        ) : null}
      </nav>

      {imgs.length ? (
        <CarPhotoGallery
          images={imgs}
          title={title}
          sourceKey={typeof d.source === "string" ? d.source : null}
        />
      ) : null}

      <CarHeroMeta title={title} data={d as Record<string, unknown>} />

      <div className="mt-8 flex flex-col gap-8 lg:flex-row lg:items-start lg:gap-10">
        <div className="min-w-0 flex-1">
          <CarTrustStrip />

          {description ? (
            <section className="rounded-2xl border border-border bg-card p-4 shadow-sm ring-1 ring-border/40 sm:p-5">
              <h2 className="font-heading text-base font-semibold tracking-tight">Описание</h2>
              <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground [overflow-wrap:anywhere]">
                {description}
              </p>
            </section>
          ) : null}

          {typeof d.dongchedi_msrp_rub === "number" && d.dongchedi_msrp_rub > 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">
              Ориентир новой (КНР, MSRP): {formatPriceLabel(d.dongchedi_msrp_rub)}
            </p>
          ) : null}

          <CarDetailAccordions data={d as Record<string, unknown>} diagnosisPhotosCount={diagnosisPhotosCount} />
        </div>

        <div className="w-full shrink-0 lg:w-[320px]">
          <CarPurchaseSidebar
            carId={carId}
            title={title}
            priceRub={rubPrice != null && !Number.isNaN(rubPrice) ? rubPrice : null}
            sourceUrl={sourceUrl}
            priceWon={priceWon != null && !Number.isNaN(priceWon) ? priceWon : null}
            priceCny={priceCny != null && !Number.isNaN(priceCny) ? priceCny : null}
            sourceLabel={typeof d.source === "string" ? d.source : null}
          />
        </div>
      </div>

      {similar.length ? (
        <section className="mt-8">
          <h2 className="mb-3 font-heading text-lg font-semibold tracking-tight">Похожие автомобили</h2>
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {similar.map((car) => {
              const img = extractCarImageUrls((car.data ?? {}) as Record<string, unknown>)[0];
              return (
                <li
                  key={car.id}
                  className="overflow-hidden rounded-xl border border-border bg-card shadow-sm ring-1 ring-border/50"
                >
                  <Link href={`/car/${encodeURIComponent(car.id)}`} className="block">
                    <div className="overflow-hidden bg-muted">
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
                          unoptimized
                        />
                      ) : (
                        <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
                          Нет фото
                        </div>
                      )}
                    </div>
                    <p className="line-clamp-2 px-3 pt-2 text-sm font-medium">{car.title || car.id}</p>
                    <p className="px-3 pb-3 text-sm text-muted-foreground">
                      {formatSimilarPrice(car.price)}
                    </p>
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
