"use client";

import { type ReactNode, useEffect, useMemo, useState } from "react";
import { ChevronsUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type EngineType = "petrol" | "diesel" | "electric" | "hybrid";
type HybridType = "none" | "parallel" | "series";
type Currency = "USD" | "EUR" | "JPY" | "KRW" | "CNY";
type AgeRange = "0-3" | "3-5" | "5+";
type Purpose = "personal" | "resale" | "legal";

type CbrRate = { Value: number; Nominal: number };

const FALLBACK_RATES: Record<Currency, CbrRate> = {
  USD: { Value: 76.0861, Nominal: 1 },
  EUR: { Value: 89.4113, Nominal: 1 },
  JPY: { Value: 0.4793, Nominal: 1 },
  KRW: { Value: 0.0539, Nominal: 1 },
  CNY: { Value: 11.7439, Nominal: 1 },
};

function clampNumber(v: number): number {
  return Number.isFinite(v) ? Math.max(0, v) : 0;
}

function money(n: number): string {
  return `${Math.round(clampNumber(n)).toLocaleString("ru-RU")} ₽`;
}

function dutyUnder3(rub: number, eurRate: number, vol: number): number {
  const eurVal = rub / eurRate;
  let p = 0.48;
  let min = 20;
  if (eurVal <= 8500) {
    p = 0.54;
    min = 2.5;
  } else if (eurVal <= 16700) {
    p = 0.48;
    min = 3.5;
  } else if (eurVal <= 42300) {
    p = 0.48;
    min = 5.5;
  } else if (eurVal <= 84500) {
    p = 0.48;
    min = 7.5;
  } else if (eurVal <= 169000) {
    p = 0.48;
    min = 15;
  }
  return Math.max(eurVal * p, min * vol) * eurRate;
}

function dutyRate(age: AgeRange, vol: number): number {
  if (age === "3-5") {
    if (vol < 1000) return 1.5;
    if (vol <= 1500) return 1.7;
    if (vol <= 1800) return 2.5;
    if (vol <= 2300) return 2.7;
    if (vol <= 3000) return 3.0;
    return 3.6;
  }
  if (age === "5+") {
    if (vol < 1000) return 3.0;
    if (vol <= 1500) return 3.2;
    if (vol <= 1800) return 3.5;
    if (vol <= 2300) return 4.8;
    if (vol <= 3000) return 5.0;
    return 5.7;
  }
  return 0;
}

function getDuty(rub: number, eurRate: number, age: AgeRange, vol: number, engType: EngineType): number {
  if (engType === "electric") return rub * 0.15;
  if (age === "0-3") return dutyUnder3(rub, eurRate, vol);
  return dutyRate(age, vol) * vol * eurRate;
}

function getUtil(
  age: AgeRange,
  engType: EngineType,
  hybridType: HybridType,
  vol: number,
  hpIce: number,
  hpEd: number,
  purpose: Purpose,
): number {
  const base = 20000;
  const isPersonal = purpose === "personal";

  let effectivePower = 0;
  if (engType === "electric") {
    effectivePower = hpEd * 0.45;
  } else if (engType === "hybrid") {
    effectivePower = hybridType === "series" ? hpEd * 0.45 : hpIce + hpEd;
  } else {
    effectivePower = hpIce;
  }

  if (isPersonal) {
    let isLoyal = false;
    if (engType === "electric" || (engType === "hybrid" && hybridType === "series")) {
      isLoyal = effectivePower <= 80;
    } else {
      isLoyal = effectivePower <= 160;
    }
    if (isLoyal) {
      return age === "0-3" ? 3400 : 5200;
    }
  }

  const powerKw = effectivePower * 0.7355;
  let coeff = 1;
  if (age === "0-3") {
    if (vol <= 1000) {
      if (powerKw <= 50) coeff = 1.63;
      else if (powerKw <= 100) coeff = 1.85;
      else coeff = 2.08;
    } else if (vol <= 2000) {
      if (powerKw <= 100) coeff = 3.01;
      else if (powerKw <= 150) coeff = 3.62;
      else coeff = 4.23;
    } else if (vol <= 3000) {
      if (powerKw <= 150) coeff = 5.86;
      else if (powerKw <= 220) coeff = 6.47;
      else coeff = 120.12;
    } else if (vol <= 3500) {
      if (powerKw <= 200) coeff = 9.23;
      else if (powerKw <= 220) coeff = 10.05;
      else coeff = 144.0;
    } else {
      coeff = 12.29;
    }
  } else if (age === "3-5") {
    if (vol <= 1000) coeff = 5.73;
    else if (vol <= 2000) coeff = 8.95;
    else if (vol <= 3000) {
      if (powerKw > 161.8) coeff = 177.6;
      else if (powerKw > 117.7) coeff = 74.64;
      else coeff = 32.0;
    } else if (vol <= 3500) {
      coeff = 45.0;
    } else {
      coeff = 60.0;
    }
  } else {
    if (vol <= 1000) coeff = 17.5;
    else if (vol <= 2000) coeff = 28.5;
    else if (vol <= 3000) {
      if (powerKw > 161.8) coeff = 177.6;
      else if (powerKw > 117.7) coeff = 74.64;
      else coeff = 85.0;
    } else if (vol <= 3500) {
      coeff = 120.0;
    } else {
      coeff = 150.0;
    }
  }

  return Math.round(base * coeff);
}

function getCustomsFee(v: number): number {
  if (v <= 200000) return 1231;
  if (v <= 450000) return 2462;
  if (v <= 1200000) return 4924;
  if (v <= 2700000) return 8541;
  if (v <= 4200000) return 12000;
  if (v <= 10000000) return 13541;
  return 73860;
}

function SelectField({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <label className="block text-sm font-medium text-foreground">
      {label}
      <div className="relative mt-1">
        <select
          className="h-9 w-full appearance-none rounded-3xl border border-transparent bg-input/50 px-3 pe-10 text-sm transition-[color,box-shadow,background-color] outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        >
          {children}
        </select>
        <ChevronsUpDown className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground/80" />
      </div>
    </label>
  );
}

export function BuyCalculator() {
  const [engineType, setEngineType] = useState<EngineType>("petrol");
  const [hybridType, setHybridType] = useState<HybridType>("none");
  const [currency, setCurrency] = useState<Currency>("USD");
  const [price, setPrice] = useState(1_800_000);
  const [volume, setVolume] = useState(1800);
  const [hpSingle, setHpSingle] = useState(120);
  const [hpIce, setHpIce] = useState(98);
  const [hpEd, setHpEd] = useState(82);
  const [ageRange, setAgeRange] = useState<AgeRange>("5+");
  const [purpose, setPurpose] = useState<Purpose>("personal");
  const [calcNonce, setCalcNonce] = useState(0);
  const [cbrRates, setCbrRates] = useState<Record<Currency, CbrRate>>(FALLBACK_RATES);
  const [rateDateBadge, setRateDateBadge] = useState("Курсы ЦБ РФ (резервные)");

  useEffect(() => {
    const fetchExchangeRates = async () => {
      try {
        const r = await fetch(`/api/cbr-rates?ts=${Date.now()}`, { cache: "no-store" });
        if (!r.ok) throw new Error(`rate_http_${r.status}`);
        const d = await r.json();
        const valute = d?.valute || {};
        const nextRates: Record<Currency, CbrRate> = {
          USD: valute.USD ?? FALLBACK_RATES.USD,
          EUR: valute.EUR ?? FALLBACK_RATES.EUR,
          JPY: valute.JPY ?? FALLBACK_RATES.JPY,
          KRW: valute.KRW ?? FALLBACK_RATES.KRW,
          CNY: valute.CNY ?? FALLBACK_RATES.CNY,
        };
        setCbrRates(nextRates);
        const date = d?.date ? new Date(d.date).toLocaleDateString("ru-RU") : "";
        if (d?.source === "cbr") {
          setRateDateBadge(`Курсы ЦБ РФ ${date}`);
        } else {
          setRateDateBadge("Курсы ЦБ РФ (резервные)");
        }
      } catch {
        setCbrRates(FALLBACK_RATES);
        setRateDateBadge("Курсы ЦБ РФ (резервные)");
      }
    };
    void fetchExchangeRates();
  }, []);

  const result = useMemo(() => {
    const rate = cbrRates[currency].Value / cbrRates[currency].Nominal;
    const eurRate = cbrRates.EUR.Value / cbrRates.EUR.Nominal;
    const safePrice = clampNumber(price);
    const safeVol = clampNumber(volume);
    const safeHpSingle = clampNumber(hpSingle);
    const safeHpIce = clampNumber(hpIce);
    const safeHpEd = clampNumber(hpEd);

    let finalHpIce = safeHpSingle;
    let finalHpEd = 0;
    if (engineType === "hybrid" || engineType === "electric") {
      finalHpIce = safeHpIce;
      finalHpEd = safeHpEd;
    }

    const rub = safePrice * rate;
    const duty = getDuty(rub, eurRate, ageRange, safeVol, engineType);
    const util = getUtil(ageRange, engineType, hybridType, safeVol, finalHpIce, finalHpEd, purpose);
    const customsFee = getCustomsFee(rub);
    const total = duty + util + customsFee;
    const hp30Min = finalHpEd * 0.45;

    return { rate, eurRate, rub, duty, util, customsFee, total, hp30Min };
  }, [ageRange, calcNonce, cbrRates, currency, engineType, hpEd, hpIce, hpSingle, hybridType, price, purpose, volume]);

  return (
    <section className="rounded-3xl border border-border/60 bg-card/80 p-5 shadow-sm ring-1 ring-black/[0.03] backdrop-blur-sm dark:ring-white/[0.06] sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 className="text-xl font-semibold tracking-tight text-foreground">Растаможка авто в РФ</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Бензин, дизель, гибриды и электромобили — физические лица
          </p>
        </div>
        <span className="rounded-full border border-border/70 bg-muted/60 px-3 py-1 text-xs text-muted-foreground">
          {rateDateBadge}
        </span>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          <SelectField
            label="Тип двигателя"
            value={engineType}
            onChange={(raw) => {
              const v = raw as EngineType;
              setEngineType(v);
              if (v !== "hybrid") setHybridType("none");
            }}
          >
            <option value="petrol">Бензиновый</option>
            <option value="diesel">Дизельный</option>
            <option value="electric">Электрический</option>
            <option value="hybrid">Гибрид</option>
          </SelectField>

          {engineType === "hybrid" ? (
            <SelectField label="Тип гибрида" value={hybridType} onChange={(v) => setHybridType(v as HybridType)}>
              <option value="parallel">Параллельный (HEV/PHEV)</option>
              <option value="series">Последовательный (ДВС-генератор)</option>
            </SelectField>
          ) : null}

          <SelectField label="Валюта цены" value={currency} onChange={(v) => setCurrency(v as Currency)}>
            <option value="USD">Доллар (USD)</option>
            <option value="EUR">Евро (EUR)</option>
            <option value="JPY">Йена (JPY)</option>
            <option value="KRW">Вона (KRW)</option>
            <option value="CNY">Юань (CNY)</option>
          </SelectField>

          <label className="block text-sm font-medium text-foreground">
            Цена авто
            <Input
              className="mt-1 h-10"
              type="number"
              value={price}
              step={1000}
              onChange={(e) => setPrice(Number(e.target.value || 0))}
            />
          </label>

          <label className="block text-sm font-medium text-foreground">
            Объём двигателя (см³)
            <Input
              className="mt-1 h-10"
              type="number"
              value={volume}
              step={50}
              onChange={(e) => setVolume(Number(e.target.value || 0))}
            />
          </label>

          {engineType === "hybrid" || engineType === "electric" ? (
            <>
              <label className="block text-sm font-medium text-foreground">
                Мощность ДВС (л.с.)
                <Input
                  className="mt-1 h-10"
                  type="number"
                  value={hpIce}
                  step={1}
                  onChange={(e) => setHpIce(Number(e.target.value || 0))}
                />
              </label>
              <label className="block text-sm font-medium text-foreground">
                Суммарная пиковая мощность ЭД (л.с.)
                <Input
                  className="mt-1 h-10"
                  type="number"
                  value={hpEd}
                  step={1}
                  onChange={(e) => setHpEd(Number(e.target.value || 0))}
                />
                <div className="mt-1 rounded-lg bg-amber-100/70 px-3 py-2 text-xs text-amber-900">
                  30-минутная мощность ЭД: {result.hp30Min.toFixed(1)} л.с.
                </div>
              </label>
            </>
          ) : (
            <label className="block text-sm font-medium text-foreground">
              Мощность (л.с.)
              <Input
                className="mt-1 h-10"
                type="number"
                value={hpSingle}
                step={1}
                onChange={(e) => setHpSingle(Number(e.target.value || 0))}
              />
            </label>
          )}

          <div className="space-y-2">
            <p className="text-sm font-medium text-foreground">Возраст авто</p>
            <div className="flex flex-wrap gap-2">
              {(["0-3", "3-5", "5+"] as const).map((age) => (
                <label
                  key={age}
                  className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border/80 bg-background/90 px-3 py-1.5 text-sm transition-colors hover:bg-muted/50"
                >
                  <input
                    type="radio"
                    name="ageRange"
                    checked={ageRange === age}
                    onChange={() => setAgeRange(age)}
                  />
                  {age === "0-3" ? "0-3 года" : age === "3-5" ? "3-5 лет" : "Старше 5 лет"}
                </label>
              ))}
            </div>
          </div>

          <SelectField label="Цель ввоза" value={purpose} onChange={(v) => setPurpose(v as Purpose)}>
            <option value="personal">личное пользование</option>
            <option value="resale">перепродажа</option>
            <option value="legal">юрлицо</option>
          </SelectField>

          <Button
            type="button"
            className="mt-1 h-10 w-full"
            onClick={() => setCalcNonce((n) => n + 1)}
          >
            Рассчитать
          </Button>
        </div>

        <div className="rounded-2xl border border-border/70 bg-muted/30 p-4 sm:p-5">
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between gap-3 border-b border-border/60 py-2">
              <span>Курс ЦБ РФ</span>
              <span className="text-right">
                1 {currency} = {result.rate.toFixed(4)} ₽, EUR = {result.eurRate.toFixed(4)} ₽
              </span>
            </div>
            <div className="flex items-center justify-between gap-3 border-b border-border/60 py-2">
              <span>Цена в рублях</span>
              <span>{money(result.rub)}</span>
            </div>
            <div className="flex items-center justify-between gap-3 border-b border-border/60 py-2">
              <span>Таможенная стоимость</span>
              <span>{money(result.rub)}</span>
            </div>
            <div className="flex items-center justify-between gap-3 border-b border-border/60 py-2">
              <span>Таможенная пошлина</span>
              <span>{money(result.duty)}</span>
            </div>
            <div className="flex items-center justify-between gap-3 border-b border-border/60 py-2">
              <span>Утилизационный сбор</span>
              <span>{money(result.util)}</span>
            </div>
            <div className="flex items-center justify-between gap-3 border-b border-border/60 py-2">
              <span>Таможенный сбор</span>
              <span>{money(result.customsFee)}</span>
            </div>
          </div>

          <div className="mt-4 rounded-xl bg-amber-100/70 px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-semibold text-amber-900">ИТОГО РАСТАМОЖКА</span>
              <span className="text-2xl font-extrabold text-amber-700">{money(result.total)}</span>
            </div>
          </div>

          <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
            Для последовательных гибридов учитывается 30-минутная мощность ЭД. Для параллельных — суммарная мощность
            ДВС+ЭД. Льгота физлицам: до 160 л.с. (ДВС) или до 80 л.с. по 30-минутной мощности.
          </p>
        </div>
      </div>
    </section>
  );
}
