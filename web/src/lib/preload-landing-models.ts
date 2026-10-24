"use client";

import { useGLTF } from "@react-three/drei";
import { HOME_LANDING_MEDIA } from "@/lib/home-landing-media";

if (typeof window !== "undefined") {
  useGLTF.preload(HOME_LANDING_MEDIA.hero.model);
}
