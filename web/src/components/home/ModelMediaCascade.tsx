"use client";

import { MarketModelViewer } from "@/components/home/MarketModelViewer";
import type { MediaCascade } from "@/lib/home-landing-media";
import { canUseWebGL } from "@/lib/media-cascade-capabilities";
import { motion, useReducedMotion } from "framer-motion";
import { Component, type ReactNode, useCallback, useEffect, useRef, useState } from "react";

/** Сколько ждать 3D до показа fallback (мс). */
const MODEL_FALLBACK_DELAY_MS = 8_000;

const FRAME_CLASS =
  "relative mx-auto w-full min-h-[min(56vw,320px)] h-[min(56vw,320px)] sm:min-h-[380px] sm:h-[380px] lg:min-h-[min(48vh,460px)] lg:h-[min(48vh,460px)]";

const MEDIA_CLASS =
  "pointer-events-none absolute inset-0 h-full w-full object-contain object-center";

type Tier = "model" | "video" | "image";

type ModelMediaCascadeProps = {
  media: MediaCascade;
  autoRotate?: boolean;
  autoRotateDelayMs?: number;
  className?: string;
  priorityImage?: boolean;
  /** Задержка fallback для hero (мс). По умолчанию 8 с. */
  fallbackDelayMs?: number;
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

function resolveInitialTier(): Tier {
  if (typeof window === "undefined") return "model";
  if (!canUseWebGL()) return "video";
  return "model";
}

export function ModelMediaCascade({
  media,
  autoRotate = false,
  autoRotateDelayMs = 700,
  className = "",
  priorityImage = false,
  fallbackDelayMs = MODEL_FALLBACK_DELAY_MS,
}: ModelMediaCascadeProps) {
  const reduceMotion = useReducedMotion();
  const [tier, setTier] = useState<Tier>("model");
  const [modelReady, setModelReady] = useState(false);
  const [showFallback, setShowFallback] = useState(false);
  const [videoReady, setVideoReady] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const fallbackTimerRef = useRef<number | null>(null);
  const failTimerRef = useRef<number | null>(null);
  const modelLoadedRef = useRef(false);
  const cascadeKey = `${media.model}|${media.video}|${media.image}`;

  const clearTimers = useCallback(() => {
    if (fallbackTimerRef.current !== null) {
      window.clearTimeout(fallbackTimerRef.current);
      fallbackTimerRef.current = null;
    }
    if (failTimerRef.current !== null) {
      window.clearTimeout(failTimerRef.current);
      failTimerRef.current = null;
    }
  }, []);

  const failModel = useCallback(() => {
    if (modelLoadedRef.current) return;
    clearTimers();
    setModelReady(false);
    setShowFallback(true);
    setTier((t) => (t === "model" ? "video" : t));
  }, [clearTimers]);

  const failVideo = useCallback(() => {
    setVideoFailed(true);
    setTier((t) => (t === "video" ? "image" : t));
  }, []);

  const handleModelLoaded = useCallback(() => {
    modelLoadedRef.current = true;
    setModelReady(true);
    setShowFallback(false);
    clearTimers();
  }, [clearTimers]);

  useEffect(() => {
    modelLoadedRef.current = false;
    setModelReady(false);
    setShowFallback(false);
    setVideoReady(false);
    setVideoFailed(false);
    clearTimers();

    const next = resolveInitialTier();
    setTier(next);

    if (next !== "model") {
      setShowFallback(true);
      return;
    }

    fallbackTimerRef.current = window.setTimeout(() => {
      if (!modelLoadedRef.current) setShowFallback(true);
    }, fallbackDelayMs);

    failTimerRef.current = window.setTimeout(failModel, fallbackDelayMs);

    return clearTimers;
  }, [cascadeKey, failModel, clearTimers, fallbackDelayMs]);

  const showModel = tier === "model";
  const showVideo = tier === "video" && !videoFailed;
  const showImage =
    tier === "image" ||
    (showFallback && showModel && !modelReady) ||
    (showVideo && !videoReady);

  return (
    <motion.div
      className={`relative w-full bg-transparent shadow-none ${className}`}
      initial={reduceMotion ? false : { opacity: 0, x: 28 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className={FRAME_CLASS}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={media.image}
          alt=""
          decoding="async"
          fetchPriority={priorityImage ? "high" : "auto"}
          className={`${MEDIA_CLASS} transition-opacity duration-700 ${
            showImage ? "z-[1] opacity-100" : "z-[1] opacity-0"
          }`}
        />

        {showVideo && (
          <video
            autoPlay
            muted
            loop
            playsInline
            preload="auto"
            poster={media.image}
            className={`${MEDIA_CLASS} z-[2] transition-opacity duration-700 ${
              videoReady ? "opacity-100" : "opacity-0"
            }`}
            onCanPlay={() => setVideoReady(true)}
            onLoadedData={() => setVideoReady(true)}
            onError={failVideo}
          >
            <source src={media.video} type="video/webm" />
          </video>
        )}

        {showModel && (
          <ModelErrorBoundary key={cascadeKey} onError={failModel}>
            <MarketModelViewer
              modelUrl={media.model}
              autoRotate={autoRotate}
              autoRotateDelayMs={autoRotateDelayMs}
              fill
              onLoaded={handleModelLoaded}
              onContextLost={failModel}
              className="z-[3]"
            />
          </ModelErrorBoundary>
        )}
      </div>
    </motion.div>
  );
}
