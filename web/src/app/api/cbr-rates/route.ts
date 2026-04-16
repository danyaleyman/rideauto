import { NextResponse } from "next/server";

export const revalidate = 0;
export const dynamic = "force-dynamic";

const CBR_URL = "https://www.cbr-xml-daily.ru/daily_json.js";

type CbrRate = { Value: number; Nominal: number };
type CbrPayload = { Date?: string; Valute?: Record<string, CbrRate> };

const FALLBACK_RATES: Record<string, CbrRate> = {
  USD: { Value: 76.0861, Nominal: 1 },
  EUR: { Value: 89.4113, Nominal: 1 },
  JPY: { Value: 0.4793, Nominal: 1 },
  KRW: { Value: 0.0539, Nominal: 1 },
  CNY: { Value: 11.7439, Nominal: 1 },
};

export async function GET() {
  try {
    const r = await fetch(CBR_URL, { cache: "no-store" });
    if (!r.ok) throw new Error(`cbr_http_${r.status}`);
    const d = (await r.json()) as CbrPayload;
    const valute = d?.Valute ?? {};
    const out = {
      date: d?.Date ?? new Date().toISOString(),
      valute: {
        USD: valute.USD ?? FALLBACK_RATES.USD,
        EUR: valute.EUR ?? FALLBACK_RATES.EUR,
        JPY: valute.JPY ?? FALLBACK_RATES.JPY,
        KRW: valute.KRW ?? FALLBACK_RATES.KRW,
        CNY: valute.CNY ?? FALLBACK_RATES.CNY,
      },
      source: "cbr",
    };
    return NextResponse.json(out, {
      headers: { "Cache-Control": "no-store, max-age=0" },
    });
  } catch {
    return NextResponse.json(
      {
        date: new Date().toISOString(),
        valute: FALLBACK_RATES,
        source: "fallback",
      },
      { headers: { "Cache-Control": "no-store, max-age=0" } },
    );
  }
}
