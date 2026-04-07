import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LegacyCarScripts } from "@/components/legacy-car/LegacyCarScripts";
import { fetchCar } from "@/lib/api";

type PageProps = {
  params: Promise<{ ref: string }>;
};

const TOP = path.join(process.cwd(), "src/legacy/car-top.fragment.html");
const FOOTER = path.join(process.cwd(), "src/legacy/car-footer.fragment.html");

function readFrag(p: string): string {
  try {
    return fs.readFileSync(p, "utf8");
  } catch {
    return "";
  }
}

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

function bootstrapInline(ref: string): string {
  const idJson = JSON.stringify(ref);
  return `(function(){try{window.WRA_USE_NEXT_CAR_ROUTES=true;var id=${idJson};window.__WRA_NEXT_CAR_ID__=id;function pre(href){var l=document.createElement("link");l.rel="preload";l.as="fetch";l.crossOrigin="anonymous";l.href=href;document.head.appendChild(l);}pre("/api/car/"+encodeURIComponent(id));pre("/api/similar?car_id="+encodeURIComponent(id)+"&limit=8");}catch(e){}})();`;
}

function adminInline(): string {
  return "window.WRA_ADMIN_TELEGRAM_IDS=window.WRA_ADMIN_TELEGRAM_IDS||[377261863];window.WRA_ADMIN_TELEGRAM_USERNAMES=window.WRA_ADMIN_TELEGRAM_USERNAMES||[\"daniilleyman\"];window.WRA_CHANNEL_EXPORT_REPORT_BASE=window.WRA_CHANNEL_EXPORT_REPORT_BASE||\"\";";
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { ref } = await params;
  try {
    const { result } = await fetchCar(ref, { revalidate: 120 });
    if (!result || Object.keys(result).length === 0) {
      return { title: "Не найдено" };
    }
    return { title: carHeading(result) };
  } catch {
    return { title: "Карточка" };
  }
}

export default async function LegacyCarPage({ params }: PageProps) {
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

  const topHtml = readFrag(TOP);
  const footerHtml = readFrag(FOOTER);
  if (!topHtml) {
    throw new Error(
      "Нет src/legacy/car-top.fragment.html — выполните npm run sync-legacy в каталоге web/",
    );
  }

  return (
    <>
      <script dangerouslySetInnerHTML={{ __html: bootstrapInline(ref) }} />
      <script dangerouslySetInnerHTML={{ __html: adminInline() }} />
      <div dangerouslySetInnerHTML={{ __html: topHtml }} />
      <LegacyCarScripts carRef={ref} />
      {footerHtml ? <div dangerouslySetInnerHTML={{ __html: footerHtml }} /> : null}
    </>
  );
}
