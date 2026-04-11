import Image from "next/image";
import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { fetchCar, fetchSimilar } from "@/lib/api";
import { buildCarMetadata, carHeading, pickCarData } from "@/lib/car-seo";
import { formatPriceLabel, PRICE_ON_REQUEST_RU } from "@/lib/format-price";
import { getAllCarPhotoUrls } from "@/lib/car-gallery-images";
import type { SlimCar } from "@/lib/types";
import CarPhotoGallery from "@/components/car/CarPhotoGallery";
import { CarDetailAccordions } from "@/components/car/CarDetailAccordions";
import { CarPageSectionNav } from "@/components/car/CarPageSectionNav";
import { CarPurchaseSidebar } from "@/components/car/CarPurchaseSidebar";
import { CarHeroMeta } from "@/components/car/CarHeroMeta";
import { CarStickyMobileBar } from "@/components/car/CarStickyMobileBar";
import { extractCarImageUrls } from "@/lib/car-images";
import { Button } from "@/components/ui/button";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

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

  const rubFinite = rubPrice != null && !Number.isNaN(rubPrice) && rubPrice > 0;
  const priceOnRequest =
    d.price_on_request === true ||
    !rubFinite;

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

  const sourceLabelStr = typeof d.source === "string" ? d.source : null;

  const priceLine = priceOnRequest ? PRICE_ON_REQUEST_RU : formatPriceLabel(rubPrice);

  return (
    <div className="min-h-screen overflow-x-hidden bg-gradient-to-b from-muted/40 via-background to-background pb-32 pt-2 sm:pt-4 lg:pb-14">
      <div className="relative mx-auto min-w-0 max-w-[1440px] px-3 sm:px-6 lg:px-10">
        <div className="mb-5 flex min-w-0 flex-col gap-3 rounded-2xl border border-border/50 bg-card/70 px-3 py-3 shadow-sm backdrop-blur-sm sm:mb-6 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-4 sm:px-5">
          <Breadcrumb className="min-w-0 flex-1">
            <BreadcrumbList className="flex-wrap gap-x-1 gap-y-1 sm:flex-nowrap">
              <BreadcrumbItem>
                <BreadcrumbLink asChild>
                  <Link href="/">Главная</Link>
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbLink asChild>
                  <Link href="/catalog">Каталог</Link>
                </BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem className="min-w-0 max-w-full">
                <BreadcrumbPage className="line-clamp-2 break-words text-start font-medium [overflow-wrap:anywhere] sm:line-clamp-1">
                  {title}
                </BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
          {typeof d.dongchedi_specs_url === "string" && d.dongchedi_specs_url.trim() ? (
            <Button variant="outline" size="sm" className="h-auto min-h-9 w-full shrink-0 whitespace-normal rounded-xl px-3 py-2 text-center text-xs shadow-sm sm:h-9 sm:w-auto sm:rounded-full sm:text-sm" asChild>
              <a href={d.dongchedi_specs_url} target="_blank" rel="noopener noreferrer">
                Параметры модели (Dongchedi)
              </a>
            </Button>
          ) : null}
        </div>

        {imgs.length ? (
          <CarPhotoGallery
            images={imgs}
            title={title}
            sourceKey={typeof d.source === "string" ? d.source : null}
          />
        ) : null}

        <CarHeroMeta
          title={title}
          data={d as Record<string, unknown>}
          sourceLabel={sourceLabelStr}
        />

        <CarPageSectionNav hasDescription={!!description} hasSimilar={similar.length > 0} />

        <div className="flex min-w-0 flex-col gap-8 lg:flex-row lg:items-start lg:gap-12">
          <div className="min-w-0 flex-1 space-y-6 sm:space-y-8">
            {description ? (
              <section
                id="car-description"
                className="scroll-mt-20 rounded-2xl border border-border/65 bg-card p-4 shadow-sm ring-1 ring-black/[0.03] dark:ring-white/[0.06] sm:scroll-mt-24 sm:rounded-3xl sm:p-6 lg:scroll-mt-32"
              >
                <h2 className="font-heading text-lg font-semibold tracking-tight">Описание</h2>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground [overflow-wrap:anywhere]">
                  {description}
                </p>
              </section>
            ) : null}

            {typeof d.dongchedi_msrp_rub === "number" && d.dongchedi_msrp_rub > 0 ? (
              <p className="rounded-2xl border border-dashed border-border/60 bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
                Ориентир новой (КНР, MSRP):{" "}
                <span className="font-semibold tabular-nums text-foreground">
                  {formatPriceLabel(d.dongchedi_msrp_rub)}
                </span>
              </p>
            ) : null}

            <section id="car-details" className="scroll-mt-20 sm:scroll-mt-24 lg:scroll-mt-32">
              <CarDetailAccordions data={d as Record<string, unknown>} diagnosisPhotosCount={diagnosisPhotosCount} />
            </section>
          </div>

          <div className="w-full min-w-0 shrink-0 lg:w-[min(100%,380px)] xl:w-[400px]">
            <CarPurchaseSidebar
              carId={carId}
              title={title}
              priceRub={rubFinite ? rubPrice : null}
              priceOnRequest={priceOnRequest}
              sourceUrl={sourceUrl}
              priceWon={priceWon != null && !Number.isNaN(priceWon) ? priceWon : null}
              priceCny={priceCny != null && !Number.isNaN(priceCny) ? priceCny : null}
              sourceLabel={sourceLabelStr}
            />
          </div>
        </div>
      </div>

      <CarStickyMobileBar priceLine={priceLine} />

      {similar.length ? (
        <div
          id="car-similar"
          className="relative mx-auto mt-12 min-w-0 max-w-[1440px] scroll-mt-20 border-t border-border/60 px-3 pb-6 pt-8 sm:scroll-mt-24 sm:px-6 sm:pt-10 lg:scroll-mt-32 lg:px-10"
        >
          <h2 className="font-heading text-lg font-semibold tracking-tight sm:text-xl md:text-2xl">
            Похожие автомобили
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">Подборка по соседним позициям в каталоге</p>
          <ul className="mt-5 grid min-w-0 grid-cols-1 gap-4 sm:mt-6 sm:grid-cols-2 sm:gap-5 lg:grid-cols-3 xl:grid-cols-4">
            {similar.map((car) => {
              const img = extractCarImageUrls((car.data ?? {}) as Record<string, unknown>)[0];
              return (
                <li key={car.id}>
                  <Link
                    href={`/car/${encodeURIComponent(car.id)}`}
                    className="group block min-w-0 overflow-hidden rounded-2xl border border-border/65 bg-card shadow-sm ring-1 ring-black/[0.03] transition-all hover:-translate-y-0.5 hover:border-border hover:shadow-md active:scale-[0.99] dark:ring-white/[0.05]"
                  >
                    <div className="overflow-hidden bg-muted">
                      {img ? (
                        <Image
                          src={img}
                          alt={car.title || car.id}
                          width={640}
                          height={320}
                          sizes="(min-width: 1280px) 22vw, (min-width: 1024px) 28vw, (min-width: 640px) 44vw, 96vw"
                          className="h-44 w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
                          loading="lazy"
                          decoding="async"
                          unoptimized
                        />
                      ) : (
                        <div className="flex h-44 items-center justify-center text-sm text-muted-foreground">
                          Нет фото
                        </div>
                      )}
                    </div>
                    <div className="min-w-0 p-3 sm:p-3.5">
                      <p className="line-clamp-3 break-words text-sm font-semibold leading-snug [overflow-wrap:anywhere] group-hover:text-primary sm:line-clamp-2">
                        {car.title || car.id}
                      </p>
                      <p className="mt-2 break-words text-sm font-medium tabular-nums text-muted-foreground [overflow-wrap:anywhere]">
                        {formatSimilarPrice(car.price)}
                      </p>
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
