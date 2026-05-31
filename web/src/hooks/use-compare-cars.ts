"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "wra-compare-car-ids-v1";
export const MAX_COMPARE = 4;

function loadIds(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as string[];
    return Array.isArray(parsed) ? parsed.filter(Boolean).slice(0, MAX_COMPARE) : [];
  } catch {
    return [];
  }
}

function persistIds(ids: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ids.slice(0, MAX_COMPARE)));
}

export function useCompareCars() {
  const [ids, setIds] = useState<string[]>([]);

  useEffect(() => {
    setIds(loadIds());
  }, []);

  const add = useCallback((carId: string) => {
    setIds((prev) => {
      if (prev.includes(carId)) return prev;
      const next = [carId, ...prev].slice(0, MAX_COMPARE);
      persistIds(next);
      return next;
    });
  }, []);

  const remove = useCallback((carId: string) => {
    setIds((prev) => {
      const next = prev.filter((x) => x !== carId);
      persistIds(next);
      return next;
    });
  }, []);

  const toggle = useCallback((carId: string) => {
    setIds((prev) => {
      if (prev.includes(carId)) {
        const next = prev.filter((x) => x !== carId);
        persistIds(next);
        return next;
      }
      if (prev.length >= MAX_COMPARE) return prev;
      const next = [carId, ...prev];
      persistIds(next);
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    persistIds([]);
    setIds([]);
  }, []);

  const compareHref = useMemo(() => {
    if (!ids.length) return "/compare";
    return `/compare?ids=${ids.map((id) => encodeURIComponent(id)).join(",")}`;
  }, [ids]);

  const isInCompare = useCallback((carId: string) => ids.includes(carId), [ids]);

  return {
    ids,
    add,
    remove,
    toggle,
    clear,
    compareHref,
    isInCompare,
    count: ids.length,
    full: ids.length >= MAX_COMPARE,
  };
}
