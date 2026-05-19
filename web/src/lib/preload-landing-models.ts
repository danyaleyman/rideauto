"use client";

import { useGLTF } from "@react-three/drei";
import { HOME_LANDING_MEDIA } from "@/lib/home-landing-media";

if (typeof window !== "undefined") {
  useGLTF.preload(HOME_LANDING_MEDIA.hero.model);
  useGLTF.preload(HOME_LANDING_MEDIA.markets.korea.model);
  useGLTF.preload(HOME_LANDING_MEDIA.markets.china.model);
  useGLTF.preload(HOME_LANDING_MEDIA.markets.japan.model);
}
