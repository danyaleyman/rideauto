"use client";

import { MarketModelViewer } from "@/components/home/MarketModelViewer";
import type { MediaCascade } from "@/lib/home-landing-media";
import { canUseWebGL } from "@/lib/media-cascade-capabilities";
import { motion, useReducedMotion } from "framer-motion";
import { Component, type ReactNode, useCallback, useEffect, useRef, useState } from "react";

/** Таймаут загрузки GLB до перехода на video (не скрывает 3D раньше времени). */
const MODEL_LOAD_TIMEOUT_MS = 15_000;
/** Через сколько мс показать PNG под моделью, пока GLB ещё грузится. */
const FALLBACK_HINT_DELAY_MS = 7_000;

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
  fallbackDelayMs?: number;
  onSettled?: () => void;
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

export function ModelMediaCascade({
  media,
  autoRotate = false,
  autoRotateDelayMs = 700,
  className = "",
  priorityImage = false,
  fallbackDelayMs = FALLBACK_HINT_DELAY_MS,
  onSettled,
}: ModelMediaCascadeProps) {
  const reduceMotion = useReducedMotion();
  const [tier, setTier] = useState<Tier>("model");
  const [modelReady, setModelReady] = useState(false);
  const [showFallbackHint, setShowFallbackHint] = useState(false);
  const [videoReady, setVideoReady] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const loadTimerRef = useRef<number | null>(null);
  const hintTimerRef = useRef<number | null>(null);
  const modelLoadedRef = useRef(false);
  const cascadeKey = `${media.model}|${media.video}|${media.image}`;

  const clearTimers = useCallback(() => {
    if (loadTimerRef.current !== null) {
      window.clearTimeout(loadTimerRef.current);
      loadTimerRef.current = null;
    }
    if (hintTimerRef.current !== null) {
      window.clearTimeout(hintTimerRef.current);
      hintTimerRef.current = null;
    }
  }, []);

  const failModel = useCallback(() => {
    if (modelLoadedRef.current) return;
    clearTimers();
    setModelReady(false);
    setTier((t) => (t === "model" ? "video" : t));
    onSettled?.();
  }, [clearTimers, onSettled]);

  const failVideo = useCallback(() => {
    setVideoFailed(true);
    setTier((t) => (t === "video" ? "image" : t));
    onSettled?.();
  }, [onSettled]);

  const handleModelLoaded = useCallback(() => {
    modelLoadedRef.current = true;
    setModelReady(true);
    setShowFallbackHint(false);
    clearTimers();
    onSettled?.();
  }, [clearTimers, onSettled]);

  useEffect(() => {
    modelLoadedRef.current = false;
    setModelReady(false);
    setShowFallbackHint(false);
    setVideoReady(false);
    setVideoFailed(false);
    clearTimers();

    const next = initialTier();
    setTier(next);

    if (next !== "model") {
      onSettled?.();
      return;
    }

    hintTimerRef.current = window.setTimeout(() => {
      if (!modelLoadedRef.current) setShowFallbackHint(true);
    }, fallbackDelayMs);

    loadTimerRef.current = window.setTimeout(failModel, MODEL_LOAD_TIMEOUT_MS);

    return clearTimers;
  }, [cascadeKey, failModel, clearTimers, fallbackDelayMs, onSettled]);

  useEffect(() => {
    if (tier !== "model" && tier !== "video") return;
    if (tier === "model" && !modelReady) return;
    if (tier === "video" && !videoFailed && !videoReady) return;
    onSettled?.();
  }, [tier, modelReady, videoReady, videoFailed, onSettled]);

  const showModel = tier === "model";
  const showVideo = tier === "video" && !videoFailed;
  const showImage =
    tier === "image" ||
    (showFallbackHint && !modelReady) ||
    (showVideo && !videoReady);

  return (
    <motion.div
      className={`relative w-full bg-transparent shadow-none ${className}`}
      initial={reduceMotion ? false : { opacity: 0, x: 28 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className={FRAME_CLASS}>
        {/* Мягкая «тень от пола», чтобы модель не висела в воздухе. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-[12%] bottom-[6%] z-0 h-[10%] rounded-[50%] bg-[radial-gradient(ellipse_at_center,rgba(0,0,0,0.16)_0%,rgba(0,0,0,0.06)_45%,transparent_72%)] dark:bg-[radial-gradient(ellipse_at_center,rgba(0,0,0,0.5)_0%,rgba(0,0,0,0.2)_45%,transparent_72%)]"
        />
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={media.image}
          alt=""
          decoding="async"
          fetchPriority={priorityImage ? "high" : "auto"}
          className={`${MEDIA_CLASS} transition-opacity duration-700 ${
            showImage ? "z-[1] opacity-100" : "z-[1] opacity-0 pointer-events-none"
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
              key={cascadeKey}
              modelUrl={media.model}
              autoRotate={autoRotate}
              autoRotateDelayMs={autoRotateDelayMs}
              fill
              onLoaded={handleModelLoaded}
              onFailed={failModel}
              className="z-[3]"
            />
          </ModelErrorBoundary>
        )}
      </div>
    </motion.div>
  );
}
