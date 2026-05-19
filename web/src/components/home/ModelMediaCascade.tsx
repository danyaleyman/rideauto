"use client";

import { MarketModelViewer } from "@/components/home/MarketModelViewer";
import type { MediaCascade } from "@/lib/home-landing-media";
import { canUseWebGL } from "@/lib/media-cascade-capabilities";
import { motion, useReducedMotion } from "framer-motion";
import Image from "next/image";
import { Component, type ReactNode, useCallback, useEffect, useRef, useState } from "react";

const MODEL_LOAD_TIMEOUT_MS = 12_000;

const MEDIA_CLASS =
  "pointer-events-none mx-auto h-full w-full max-h-[min(56vw,360px)] object-contain object-center sm:max-h-[400px] lg:max-h-[min(52vh,480px)]";

type Tier = "model" | "video" | "image";

type ModelMediaCascadeProps = {
  media: MediaCascade;
  autoRotate?: boolean;
  className?: string;
};

class ModelErrorBoundary extends Component<
  { children: ReactNode; onError: () => void },
  { hasError: boolean }
> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch() {
    this.props.onError();
  }

  render() {
    if (this.state.hasError) return null;
    return this.props.children;
  }
}

function initialTier(): Tier {
  if (typeof window === "undefined") return "model";
  if (!canUseWebGL()) return "video";
  return "model";
}

export function ModelMediaCascade({ media, autoRotate = false, className = "" }: ModelMediaCascadeProps) {
  const reduceMotion = useReducedMotion();
  const [tier, setTier] = useState<Tier>("model");
  const [videoReady, setVideoReady] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const loadTimerRef = useRef<number | null>(null);
  const modelLoadedRef = useRef(false);
  const cascadeKey = `${media.model}|${media.video}|${media.image}`;

  const clearLoadTimer = useCallback(() => {
    if (loadTimerRef.current !== null) {
      window.clearTimeout(loadTimerRef.current);
      loadTimerRef.current = null;
    }
  }, []);

  const failModel = useCallback(() => {
    if (modelLoadedRef.current) return;
    clearLoadTimer();
    setTier((t) => (t === "model" ? "video" : t));
  }, [clearLoadTimer]);

  const failVideo = useCallback(() => {
    setVideoFailed(true);
    setTier((t) => (t === "video" ? "image" : t));
  }, []);

  const handleModelLoaded = useCallback(() => {
    modelLoadedRef.current = true;
    clearLoadTimer();
  }, [clearLoadTimer]);

  useEffect(() => {
    modelLoadedRef.current = false;
    setVideoReady(false);
    setVideoFailed(false);
    clearLoadTimer();

    const next = initialTier();
    setTier(next);

    if (next !== "model") return;

    loadTimerRef.current = window.setTimeout(failModel, MODEL_LOAD_TIMEOUT_MS);
    return clearLoadTimer;
  }, [cascadeKey, failModel, clearLoadTimer]);

  const showVideo = tier === "video" && !videoFailed;
  const showImage = tier === "image" || (showVideo && !videoReady);

  return (
    <motion.div
      className={`relative w-full bg-transparent shadow-none ${className}`}
      initial={reduceMotion ? false : { opacity: 0, x: 28 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="relative mx-auto flex aspect-[4/3] w-full max-w-[min(100%,820px)] items-center justify-center bg-transparent sm:aspect-[16/10] lg:aspect-[16/9] lg:max-w-none">
        {tier === "model" && (
          <ModelErrorBoundary key={cascadeKey} onError={failModel}>
            <MarketModelViewer
              modelUrl={media.model}
              autoRotate={autoRotate}
              onLoaded={handleModelLoaded}
              onContextLost={failModel}
              className="!h-full !max-h-none"
            />
          </ModelErrorBoundary>
        )}

        {(tier === "video" || tier === "image") && (
          <>
            <Image
              src={media.image}
              alt=""
              width={1400}
              height={900}
              unoptimized
              priority={tier === "image"}
              className={`${MEDIA_CLASS} transition-opacity duration-500 ${
                tier === "image" || showImage ? "relative z-[1] opacity-100" : "absolute inset-0 z-[1] opacity-0"
              }`}
            />
            {showVideo && (
              <video
                autoPlay
                muted
                loop
                playsInline
                preload="auto"
                className={`absolute inset-0 z-[2] ${MEDIA_CLASS} transition-opacity duration-500 ${
                  videoReady ? "opacity-100" : "opacity-0"
                }`}
                onCanPlay={() => setVideoReady(true)}
                onLoadedData={() => setVideoReady(true)}
                onError={failVideo}
              >
                <source src={media.video} type="video/webm" />
              </video>
            )}
          </>
        )}
      </div>
    </motion.div>
  );
}
