"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { addFavoriteClient, fetchFavoritesClient, importFavoritesClient, removeFavoriteClient } from "@/lib/client-api";
import {
  readFavorites,
  FAVORITES_STORAGE_KEY,
  type FavoriteCar,
} from "@/lib/favorites-storage";
import type { SlimCar } from "@/lib/types";

export function useFavorites() {
  const { authenticated, loading } = useAuth();
  const [items, setItems] = useState<FavoriteCar[]>([]);

  const refresh = useCallback(async () => {
    if (!authenticated) {
      setItems([]);
      return;
    }
    const res = await fetchFavoritesClient();
    setItems(res.result);
  }, [authenticated]);

  useEffect(() => {
    if (loading) return;
    void refresh();
  }, [loading, refresh]);

  useEffect(() => {
    if (!authenticated || loading) return;
    const local = readFavorites();
    if (!local.length) return;
    void importFavoritesClient(local.map((x) => x.id))
      .then(() => {
        try {
          localStorage.removeItem(FAVORITES_STORAGE_KEY);
        } catch {
          // ignore
        }
        return refresh();
      })
      .catch(() => {
        // keep local copy for retry
      });
  }, [authenticated, loading, refresh]);

  const toggle = useCallback(
    async (car: SlimCar) => {
      if (!authenticated) return;
      const exists = items.some((x) => x.id === car.id);
      if (exists) await removeFavoriteClient(car.id);
      else await addFavoriteClient(car.id);
      await refresh();
    },
    [authenticated, items, refresh],
  );

  const remove = useCallback(
    async (id: string) => {
      if (!authenticated) return;
      await removeFavoriteClient(id);
      await refresh();
    },
    [authenticated, refresh],
  );

  const isFavorite = useCallback(
    (id: string) => items.some((x) => x.id === id),
    [items],
  );

  return { items, count: items.length, toggle, remove, isFavorite, enabled: authenticated };
}
