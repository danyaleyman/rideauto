import type { SlimCar } from "@/lib/types";

export const FAVORITES_STORAGE_KEY = "wra-favorites-v1";

export type FavoriteCar = {
  id: string;
  title: string;
  price: number | null;
  addedAt: number;
};

function emitChange() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event("wra-favorites-change"));
}

export function readFavorites(): FavoriteCar[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(FAVORITES_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (x): x is FavoriteCar =>
        typeof x === "object" &&
        x !== null &&
        typeof (x as FavoriteCar).id === "string" &&
        typeof (x as FavoriteCar).title === "string",
    );
  } catch {
    return [];
  }
}

function writeFavorites(items: FavoriteCar[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(items));
    emitChange();
  } catch {
    /* quota / private mode */
  }
}

export function isFavoriteId(id: string): boolean {
  return readFavorites().some((x) => x.id === id);
}

export function removeFavorite(id: string) {
  const next = readFavorites().filter((x) => x.id !== id);
  writeFavorites(next);
}

/** Возвращает true, если авто теперь в избранном. */
export function toggleFavorite(car: SlimCar): boolean {
  const cur = readFavorites();
  const exists = cur.some((x) => x.id === car.id);
  if (exists) {
    writeFavorites(cur.filter((x) => x.id !== car.id));
    return false;
  }
  const title = (car.title || car.id).trim();
  const price = car.price ?? null;
  writeFavorites([...cur, { id: car.id, title, price, addedAt: Date.now() }]);
  return true;
}
