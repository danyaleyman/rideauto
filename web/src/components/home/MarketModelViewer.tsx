"use client";

import { Bounds, Center, OrbitControls, useGLTF } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { DoubleSide, type Group, type Material, type Mesh } from "three";

const CAMERA_3_4: [number, number, number] = [4.2, 1.35, 5.4];
const LOCK_DISTANCE = 5.8;

function SceneLights() {
  return (
    <>
      <ambientLight intensity={1.2} />
      <directionalLight position={[5, 10, 7]} intensity={1.5} />
      <directionalLight position={[-3, 5, 4]} intensity={0.8} color="#fff4e8" />
      <directionalLight position={[0, 4, -6]} intensity={0.45} />
    </>
  );
}

function normalizeMaterials(object: Group) {
  object.traverse((obj) => {
    const mesh = obj as Mesh;
    if (!mesh.isMesh) return;

    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    for (const material of materials) {
      if (!material) continue;
      const mat = material as Material & {
        transmission?: number;
        thickness?: number;
        transparent?: boolean;
        opacity?: number;
        depthWrite?: boolean;
      };
      if (typeof mat.transmission === "number" && mat.transmission > 0) {
        mat.transmission = 0;
        mat.thickness = 0;
        mat.transparent = false;
        mat.opacity = 1;
        mat.depthWrite = true;
      }
      mat.side = DoubleSide;
      mat.needsUpdate = true;
    }
  });
}

function GlbModel({ url, onLoaded }: { url: string; onLoaded?: () => void }) {
  const { scene } = useGLTF(url);
  const model = useMemo(() => {
    const clone = scene.clone(true);
    normalizeMaterials(clone);
    return clone;
  }, [scene]);
  const loadedOnce = useRef(false);

  useEffect(() => {
    loadedOnce.current = false;
  }, [url]);

  useLayoutEffect(() => {
    let meshCount = 0;
    model.traverse((obj) => {
      if ((obj as Mesh).isMesh) meshCount += 1;
    });

    if (meshCount === 0 || loadedOnce.current) return;

    loadedOnce.current = true;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => onLoaded?.());
    });
  }, [model, onLoaded, url]);

  return (
    <Bounds fit clip margin={1.05} maxDuration={0}>
      <Center>
        <primitive object={model} />
      </Center>
    </Bounds>
  );
}

function Scene({
  modelUrl,
  autoRotate,
  autoRotateDelayMs,
  onLoaded,
}: {
  modelUrl: string;
  autoRotate: boolean;
  autoRotateDelayMs: number;
  onLoaded?: () => void;
}) {
  const [rotateEnabled, setRotateEnabled] = useState(false);

  useEffect(() => {
    setRotateEnabled(false);
    if (!autoRotate) return;
    const id = window.setTimeout(() => setRotateEnabled(true), autoRotateDelayMs);
    return () => window.clearTimeout(id);
  }, [autoRotate, autoRotateDelayMs, modelUrl]);

  return (
    <>
      <SceneLights />
      <Suspense fallback={null}>
        <GlbModel key={modelUrl} url={modelUrl} onLoaded={onLoaded} />
      </Suspense>
      <OrbitControls
        autoRotate={rotateEnabled}
        autoRotateSpeed={0.55}
        enableDamping
        dampingFactor={0.08}
        enablePan={false}
        enableZoom={false}
        minPolarAngle={Math.PI / 4}
        maxPolarAngle={Math.PI / 2.05}
        minDistance={LOCK_DISTANCE}
        maxDistance={LOCK_DISTANCE}
      />
    </>
  );
}

export type MarketModelViewerProps = {
  modelUrl: string;
  autoRotate?: boolean;
  autoRotateDelayMs?: number;
  fill?: boolean;
  className?: string;
  onLoaded?: () => void;
  onFailed?: () => void;
};

export function MarketModelViewer({
  modelUrl,
  autoRotate = false,
  autoRotateDelayMs = 700,
  fill = false,
  className = "",
  onLoaded,
  onFailed,
}: MarketModelViewerProps) {
  const [mounted, setMounted] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    const mq = window.matchMedia("(max-width: 767px)");
    const update = () => setIsMobile(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, [mounted]);

  const sizeClass = fill
    ? "absolute inset-0 h-full w-full"
    : "relative h-[min(56vw,320px)] w-full sm:h-[380px] lg:h-[min(48vh,460px)]";

  if (!mounted) {
    return <div className={`${sizeClass} touch-none ${className}`} aria-hidden />;
  }

  return (
    <div className={`${sizeClass} touch-none ${className}`} aria-hidden>
      <Canvas
        className="!touch-none"
        dpr={isMobile ? 1 : [1, 1.5]}
        gl={{
          antialias: !isMobile,
          alpha: true,
          powerPreference: "high-performance",
          toneMappingExposure: 1.25,
        }}
        camera={{ position: CAMERA_3_4, fov: 40, near: 0.1, far: 100 }}
        style={{ background: "transparent", touchAction: "none" }}
        onCreated={({ gl }) => {
          gl.setClearColor(0x000000, 0);
          gl.domElement.addEventListener(
            "webglcontextlost",
            (event) => {
              event.preventDefault();
              onFailed?.();
            },
            { once: true },
          );
        }}
      >
        <Scene
          modelUrl={modelUrl}
          autoRotate={autoRotate}
          autoRotateDelayMs={autoRotateDelayMs}
          onLoaded={onLoaded}
        />
      </Canvas>
    </div>
  );
}
