import type { MetadataRoute } from "next";
import { getServerApiBase, getSiteUrl } from "@/lib/env";

const PAGE_SIZE = 5000;
const MAX_SHARDS = 40;

type SitemapCar = { ref: string; updated_at: string | null };

type CarsPage = { result?: SitemapCar[]; total?: number };

async function fetchCarsPage(offset: number, limit: number): Promise<CarsPage> {
  const base = getServerApiBase();
  try {
    const res = await fetch(`${base}/api/sitemap/cars?limit=${limit}&offset=${offset}`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return { result: [], total: 0 };
    return (await res.json()) as CarsPage;
  } catch {
    return { result: [], total: 0 };
  }
}

export async function generateSitemaps() {
  const first = await fetchCarsPage(0, 1);
  const total = first.total ?? 0;
  const shards = Math.max(1, Math.min(MAX_SHARDS, Math.ceil(total / PAGE_SIZE) || 1));
  return Array.from({ length: shards }, (_, id) => ({ id }));
}

function staticRoutes(site: string, now: Date): MetadataRoute.Sitemap {
  return [
    { url: `${site}/`, lastModified: now, changeFrequency: "daily", priority: 1 },
    { url: `${site}/catalog`, lastModified: now, changeFrequency: "hourly", priority: 0.9 },
    { url: `${site}/compare`, lastModified: now, changeFrequency: "weekly", priority: 0.5 },
    { url: `${site}/buy`, lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: `${site}/contacts`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
    { url: `${site}/privacy`, lastModified: now, changeFrequency: "yearly", priority: 0.3 },
    { url: `${site}/cookies`, lastModified: now, changeFrequency: "yearly", priority: 0.3 },
  ];
}

export default async function sitemap({ id }: { id: number }): Promise<MetadataRoute.Sitemap> {
  const site = getSiteUrl();
  const now = new Date();
  const offset = id * PAGE_SIZE;
  const page = await fetchCarsPage(offset, PAGE_SIZE);
  const cars = page.result ?? [];

  const carRoutes: MetadataRoute.Sitemap = cars.map((c) => ({
    url: `${site}/car/${encodeURIComponent(c.ref)}`,
    lastModified: c.updated_at ? new Date(c.updated_at) : now,
    changeFrequency: "daily" as const,
    priority: 0.7,
  }));

  if (id === 0) {
    return [...staticRoutes(site, now), ...carRoutes];
  }
  return carRoutes;
}
