import type { Metadata } from "next";
import { getSiteUrl } from "@/lib/env";
import { asStr, buildNormalizedCarTitle } from "@/lib/car-detail-data";

export function pickCarData(raw: Record<string, unknown>): Record<string, unknown> {
  const inner = raw.data;
  if (inner && typeof inner === "object" && !Array.isArray(inner)) {
    return inner as Record<string, unknown>;
  }
  return raw;
}

export function carHeading(raw: Record<string, unknown>): string {
  const d = pickCarData(raw);
  const heading = buildNormalizedCarTitle(
    d.mark,
    d.model,
    d.generation ?? d.configuration,
    asStr(d.source) ?? asStr(raw.source),
  );
  if (heading) return heading.replace(/\s*·\s*/g, " ");
  return typeof raw.title === "string" ? raw.title : "Автомобиль";
}

function formatPriceRub(v: unknown): string | null {
  if (v == null || v === "") return null;
  const n = typeof v === "number" ? v : Number(String(v).replace(/\s/g, ""));
  if (Number.isNaN(n)) return null;
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(n);
}

function carDescription(raw: Record<string, unknown>): string {
  const d = pickCarData(raw);
  const bits: string[] = [];
  if (d.year != null && d.year !== "") bits.push(`год ${d.year}`);
  if (d.km_age != null && d.km_age !== "") bits.push(`пробег ${d.km_age} км`);
  const price = formatPriceRub(d.my_price);
  if (price) bits.push(price);
  const head = carHeading(raw);
  const tail =
    bits.length > 0
      ? `${bits.join(", ")}.`
      : "Комплектация, фото и расчёт стоимости.";
  return `${head} — ${tail} Подбор и доставка World Ride Auto.`;
}

function firstCarImage(raw: Record<string, unknown>): string | undefined {
  const d = pickCarData(raw);
  const imgs = d.images;
  if (!Array.isArray(imgs)) return undefined;
  const u = imgs.find((x): x is string => typeof x === "string" && x.length > 0);
  return u;
}

export function buildCarMetadata(ref: string, raw: Record<string, unknown>): Metadata {
  const title = carHeading(raw);
  const description = carDescription(raw);
  const img = firstCarImage(raw);
  const canonicalPath = `/car/${encodeURIComponent(ref)}`;
  const fallbackImg = new URL(
    "/image/logo%20no%20text.svg",
    `${getSiteUrl()}/`,
  ).toString();

  return {
    title,
    description,
    alternates: { canonical: canonicalPath },
    openGraph: {
      title,
      description,
      type: "website",
      url: canonicalPath,
      images: [{ url: img ?? fallbackImg }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [img ?? fallbackImg],
    },
  };
}
