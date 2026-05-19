/** Медиа главной: каскад 3D → webm → png (`web/public/assets/`). */
export type MediaCascade = {
  model: string;
  video: string;
  image: string;
};

export const HOME_LANDING_MEDIA = {
  hero: {
    // Временно: рабочая модель из карусели (вернуть hero.glb после проверки)
    model: "/assets/2025_xiaomi_yu7.glb",
    video: "/assets/hero-fallback-animation.webm",
    image: "/assets/hero-fallback-image.png",
  },
  markets: {
    korea: {
      model: "/assets/2025_hyundai_kona_n_line.glb",
      video: "/assets/china-fallback-animation.webm",
      image: "/assets/china-fallback-image.png",
    },
    china: {
      model: "/assets/2025_xiaomi_yu7.glb",
      video: "/assets/china-fallback-animation.webm",
      image: "/assets/china-fallback-image.png",
    },
    japan: {
      model: "/assets/2024_toyota_land_cruiser_250_first_edition.glb",
      video: "/assets/japan-fallback-animation.webm",
      image: "/assets/japan-fallback-image.png",
    },
  },
} as const;
