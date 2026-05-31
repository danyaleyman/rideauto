import type { Metadata } from "next";
import { getSiteUrl } from "@/lib/env";
import { asStr, buildNormalizedCarTitle } from "@/lib/car-detail-data";
import { enrichChe168CarSpecs } from "@/lib/che168-spec-enrich";
import { buildLocaleAlternates } from "@/lib/hreflang";

function pickReadModel(raw: Record<string, unknown>): Record<string, unknown> | null {
  const rm = raw.read_model;
  if (!rm || typeof rm !== "object" || Array.isArray(rm)) return null;
  return rm as Record<string, unknown>;
}

export function pickCarData(raw: Record<string, unknown>): Record<string, unknown> {
  const inner = raw.data;
  const readModel = pickReadModel(raw);
  let merged: Record<string, unknown>;
  if (inner && typeof inner === "object" && !Array.isArray(inner)) {
    const data = inner as Record<string, unknown>;
    if (!readModel) merged = { ...data };
    else {
      merged = {
        ...data,
        year: data.year ?? readModel.year ?? raw.year_num ?? raw.year,
        yearMonth:
          data.yearMonth ??
          readModel.yearMonth ??
          readModel.year_month ??
          readModel.first_registration_at,
        yearname: data.yearname ?? readModel.yearname,
        regdate: data.regdate ?? readModel.regdate,
        km_age: data.km_age ?? readModel.mileage_km,
        engine_type: data.engine_type ?? readModel.engine_type,
        transmission_type:
          data.transmission_type ??
          readModel.transmission_type ??
          readModel.transmission ??
          readModel.gearbox,
        drive_type:
          data.drive_type ??
          readModel.drive_type ??
          readModel.drivemode ??
          readModel.drive,
        body_type: data.body_type ?? readModel.body_type,
        color: data.color ?? readModel.color,
        power_hp: data.power_hp ?? readModel.power_hp ?? readModel.hp,
        displacement_cc: data.displacement_cc ?? readModel.displacement_cc,
        che168_recommended_options:
          data.options_real ??
          data.che168_recommended_options ??
          readModel.che168_recommended_options ??
          raw.options_real ??
          raw.che168_recommended_options,
        che168_options_enriched:
          data.che168_options_enriched ?? readModel.che168_options_enriched ?? raw.che168_options_enriched,
        configuration: data.configuration ?? readModel.trim_name,
        trim_name: data.trim_name ?? readModel.trim_name,
        source: data.source ?? raw.source,
      };
    }
  } else if (readModel) merged = { ...raw, ...readModel };
  else merged = raw;
  return enrichChe168CarSpecs(merged);
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

function num(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim()) {
    const n = Number(v.replace(/\s/g, ""));
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function schemaAvailability(availability: string): string {
  if (availability === "sold") return "https://schema.org/SoldOut";
  if (availability === "reserved") return "https://schema.org/LimitedAvailability";
  return "https://schema.org/InStock";
}

/**
 * schema.org/Car (+Offer) для страницы авто. Возвращает объект JSON-LD;
 * страница рендерит его в <script type="application/ld+json">.
 * Включаются только присутствующие поля (Google игнорирует пустые, но чище без них).
 */
export function buildCarJsonLd(
  ref: string,
  raw: Record<string, unknown>,
  opts: {
    priceRub: number | null;
    priceOnRequest: boolean;
    availability: string;
    images: string[];
  },
): Record<string, unknown> {
  const d = pickCarData(raw);
  const base = getSiteUrl().replace(/\/$/, "");
  const url = `${base}/car/${encodeURIComponent(ref)}`;

  const node: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "Car",
    name: carHeading(raw),
    url,
  };

  const mark = asStr(d.mark);
  if (mark) node.brand = { "@type": "Brand", name: mark };
  const model = asStr(d.model);
  if (model) node.model = model;

  const year = num(d.year);
  if (year && year > 1950 && year < 2100) {
    node.vehicleModelDate = String(year);
    node.productionDate = String(year);
  }

  const mileage = num(d.km_age);
  if (mileage != null && mileage >= 0) {
    node.mileageFromOdometer = {
      "@type": "QuantitativeValue",
      value: mileage,
      unitCode: "KMT",
    };
  }

  const transmission = asStr(d.transmission_type);
  if (transmission) node.vehicleTransmission = transmission;
  const fuel = asStr(d.fuel_type) ?? asStr(d.engine_type);
  if (fuel) node.fuelType = fuel;
  const color = asStr(d.color);
  if (color) node.color = color;
  const body = asStr(d.body_type);
  if (body) node.bodyType = body;

  const engine: Record<string, unknown> = {};
  const cc = num(d.displacement_cc);
  if (cc && cc > 0) {
    engine.engineDisplacement = { "@type": "QuantitativeValue", value: cc, unitCode: "CMQ" };
  }
  const hp = num(d.power_hp);
  if (hp && hp > 0) {
    engine.enginePower = { "@type": "QuantitativeValue", value: hp, unitCode: "BHP" };
  }
  if (Object.keys(engine).length > 0) {
    node.vehicleEngine = { "@type": "EngineSpecification", ...engine };
  }

  const images = opts.images.filter((u) => typeof u === "string" && /^https?:\/\//i.test(u)).slice(0, 8);
  if (images.length) node.image = images;

  const offer: Record<string, unknown> = {
    "@type": "Offer",
    url,
    priceCurrency: "RUB",
    availability: schemaAvailability(opts.availability),
    itemCondition: "https://schema.org/UsedCondition",
  };
  if (!opts.priceOnRequest && opts.priceRub != null && opts.priceRub > 0) {
    offer.price = Math.round(opts.priceRub);
  }
  node.offers = offer;

  return node;
}

export function buildCarMetadata(ref: string, raw: Record<string, unknown>): Metadata {
  const title = carHeading(raw);
  const description = carDescription(raw);
  const img = firstCarImage(raw);
  const canonicalPath = `/car/${encodeURIComponent(ref)}`;
  // hreflang считаем статически (без headers()) — путь детерминирован из ref.
  const { canonical, languages } = buildLocaleAlternates(canonicalPath, "");
  const fallbackImg = new URL(
    "/image/logo%20no%20text.svg",
    `${getSiteUrl()}/`,
  ).toString();

  return {
    title,
    description,
    alternates: { canonical, languages },
    openGraph: {
      title,
      description,
      type: "website",
      url: canonical,
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
