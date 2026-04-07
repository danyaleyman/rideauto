"use client";

import { useEffect } from "react";

const LEGACY_BODY = ["wra-page-gray", "text-gray-800", "antialiased"] as const;

export function CarBodyClass() {
  useEffect(() => {
    for (const c of LEGACY_BODY) document.body.classList.add(c);
    return () => {
      for (const c of LEGACY_BODY) document.body.classList.remove(c);
    };
  }, []);
  return null;
}
