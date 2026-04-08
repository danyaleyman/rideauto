import { getSiteUrl } from "@/lib/env";

/** Абсолютная ссылка на карточку авто на этом сайте (удобно для копирования и избранного). */
export function getCarPageAbsoluteUrl(carId: string): string {
  const origin =
    typeof window !== "undefined" ? window.location.origin : getSiteUrl();
  return `${origin.replace(/\/$/, "")}/car/${encodeURIComponent(carId)}`;
}
