"use client";

import { useCallback, useEffect, useState } from "react";
import {
  readFavorites,
  removeFavorite as removeStored,
  toggleFavorite as toggleStored,
  type FavoriteCar,
} from "@/lib/favorites-storage";
import type { SlimCar } from "@/lib/types";

export function useFavorites() {
  const [items, setItems] = useState<FavoriteCar[]>([]);

  useEffect(() => {
    const sync = () => setItems(readFavorites());
    sync();
    window.addEventListener("wra-favorites-change", sync);
    return () => window.removeEventListener("wra-favorites-change", sync);
  }, []);

  const toggle = useCallback((car: SlimCar) => {
    toggleStored(car);
  }, []);

  const remove = useCallback((id: string) => {
    removeStored(id);
  }, []);

  const isFavorite = useCallback(
    (id: string) => items.some((x) => x.id === id),
    [items],
  );

  return { items, count: items.length, toggle, remove, isFavorite };
}
