/**
 * Пути медиа для главной. Положите файлы в `web/public/assets/landing/`
 * с этими именами — компоненты подхватят их без правки разметки.
 */
export const HOME_LANDING_MEDIA = {
  hero: {
    poster: "/assets/hero-poster.webp",
    webm: "/assets/hero.webm",
    mp4: "/assets/hero.mp4",
    /** Будущая 3D-модель (glb/draco), подключение в HeroMedia отдельным PR */
    model: "/assets/landing/hero.glb",
  },
  scenes: {
    inspection: "/assets/landing/scene-inspection.webp",
    source: "/assets/landing/scene-source.webp",
  },
} as const;
