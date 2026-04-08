"use client";

import { useMemo, useState } from "react";

type Currency = "KRW" | "USD" | "EUR" | "RUB";
type AgeGroup = "lt3" | "3to5" | "5to7" | "gt7";
type Fuel = "petrol" | "diesel" | "hybrid" | "electric";

const RATES: Record<Currency, number> = { KRW: 0.058, USD: 95, EUR: 104, RUB: 1 };
const AGE_COEFF: Record<AgeGroup, number> = { lt3: 0.22, "3to5": 0.32, "5to7": 0.4, gt7: 0.5 };

function money(n: number): string {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(n);
}

export function BuyCalculator() {
  const [price, setPrice] = useState(3_000_000);
  const [currency, setCurrency] = useState<Currency>("KRW");
  const [engineCc, setEngineCc] = useState(2000);
  const [horsePower, setHorsePower] = useState(180);
  const [ageGroup, setAgeGroup] = useState<AgeGroup>("lt3");
  const [fuel, setFuel] = useState<Fuel>("petrol");

  const result = useMemo(() => {
    const baseRub = Math.max(0, price) * RATES[currency];
    const logistics = 280_000;
    const customs = baseRub * AGE_COEFF[ageGroup];
    const enginePart = Math.max(0, engineCc) * (fuel === "diesel" ? 120 : 90);
    const powerPart = Math.max(0, horsePower) * 700;
    const broker = 95_000;
    const subtotal = baseRub + logistics + customs + enginePart + powerPart + broker;
    const service = subtotal * 0.03;
    const total = subtotal + service;
    return { baseRub, logistics, customs, enginePart, powerPart, broker, service, total };
  }, [ageGroup, currency, engineCc, fuel, horsePower, price]);

  return (
    <section className="rounded-2xl border border-zinc-200 bg-white p-6">
      <h2 className="text-xl font-semibold text-zinc-900">Rough calculator</h2>
      <p className="mt-1 text-sm text-zinc-500">Estimate only, final quote depends on market and logistics.</p>

      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <label className="text-sm">Car price
          <input className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2" type="number" value={price} onChange={(e) => setPrice(Number(e.target.value || 0))} />
        </label>
        <label className="text-sm">Currency
          <select className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2" value={currency} onChange={(e) => setCurrency(e.target.value as Currency)}>
            <option value="KRW">KRW</option><option value="USD">USD</option><option value="EUR">EUR</option><option value="RUB">RUB</option>
          </select>
        </label>
        <label className="text-sm">Engine cc
          <input className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2" type="number" value={engineCc} onChange={(e) => setEngineCc(Number(e.target.value || 0))} />
        </label>
        <label className="text-sm">Horse power
          <input className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2" type="number" value={horsePower} onChange={(e) => setHorsePower(Number(e.target.value || 0))} />
        </label>
        <label className="text-sm">Car age
          <select className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2" value={ageGroup} onChange={(e) => setAgeGroup(e.target.value as AgeGroup)}>
            <option value="lt3">less than 3 years</option>
            <option value="3to5">3-5 years</option>
            <option value="5to7">5-7 years</option>
            <option value="gt7">more than 7 years</option>
          </select>
        </label>
        <label className="text-sm">Fuel type
          <select className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2" value={fuel} onChange={(e) => setFuel(e.target.value as Fuel)}>
            <option value="petrol">petrol</option><option value="diesel">diesel</option><option value="hybrid">hybrid</option><option value="electric">electric</option>
          </select>
        </label>
      </div>

      <dl className="mt-6 grid gap-2 text-sm text-zinc-600">
        <div className="flex justify-between"><dt>Price in RUB</dt><dd>{money(result.baseRub)}</dd></div>
        <div className="flex justify-between"><dt>Logistics</dt><dd>{money(result.logistics)}</dd></div>
        <div className="flex justify-between"><dt>Customs</dt><dd>{money(result.customs)}</dd></div>
        <div className="flex justify-between"><dt>Engine duty</dt><dd>{money(result.enginePart)}</dd></div>
        <div className="flex justify-between"><dt>Power tax</dt><dd>{money(result.powerPart)}</dd></div>
        <div className="flex justify-between"><dt>Broker/docs</dt><dd>{money(result.broker)}</dd></div>
        <div className="flex justify-between"><dt>Service fee (3%)</dt><dd>{money(result.service)}</dd></div>
      </dl>

      <p className="mt-5 rounded-xl bg-zinc-100 px-4 py-3 text-lg font-semibold text-zinc-900">
        Estimated total: {money(result.total)}
      </p>
    </section>
  );
}
