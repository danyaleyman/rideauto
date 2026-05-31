"use client";

import { useEffect, useState } from "react";

/** Высота visualViewport (клавиатура iOS/Android) → CSS var --visual-viewport-height. */
export function useVisualViewportHeight(): number {
  const [height, setHeight] = useState(() =>
    typeof window !== "undefined" ? window.innerHeight : 800,
  );

  useEffect(() => {
    const sync = () => {
      const h = window.visualViewport?.height ?? window.innerHeight;
      setHeight(h);
      document.documentElement.style.setProperty("--visual-viewport-height", `${Math.round(h)}px`);
    };
    sync();
    const vv = window.visualViewport;
    vv?.addEventListener("resize", sync);
    vv?.addEventListener("scroll", sync);
    window.addEventListener("resize", sync);
    return () => {
      vv?.removeEventListener("resize", sync);
      vv?.removeEventListener("scroll", sync);
      window.removeEventListener("resize", sync);
    };
  }, []);

  return height;
}
