import { HOME_LANDING_MEDIA } from "@/lib/home-landing-media";

let heroPreloadStarted = false;

/** Ранняя подгрузка hero GLB (fetch + drei cache). */
export function preloadHeroModel(): void {
  if (heroPreloadStarted || typeof window === "undefined") return;
  heroPreloadStarted = true;

  const url = HOME_LANDING_MEDIA.hero.model;

  void import("@react-three/drei").then(({ useGLTF }) => {
    useGLTF.preload(url);
  });

  const link = document.createElement("link");
  link.rel = "preload";
  link.as = "fetch";
  link.href = url;
  link.crossOrigin = "anonymous";
  document.head.appendChild(link);
}
