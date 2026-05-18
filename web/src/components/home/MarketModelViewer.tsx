"use client";

import { HOME_MARKETS } from "@/lib/home-markets";
import { Bounds, Center, OrbitControls, useGLTF } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { useReducedMotion } from "framer-motion";
import { Suspense, useLayoutEffect } from "react";
import type { Mesh } from "three";

function MarketGlbModel({ url }: { url: string }) {
  const { scene } = useGLTF(url);

  useLayoutEffect(() => {
    scene.traverse((obj) => {
      const mesh = obj as Mesh;
      if (mesh.isMesh) {
        mesh.castShadow = true;
        mesh.receiveShadow = true;
      }
    });
  }, [scene]);

  return (
    <Bounds fit clip margin={1.2} maxDuration={0}>
      <Center>
        <primitive object={scene} />
      </Center>
    </Bounds>
  );
}

function Scene({ modelUrl, autoRotate }: { modelUrl: string; autoRotate: boolean }) {
  return (
    <>
      <ambientLight intensity={0.55} />
      <directionalLight position={[4, 6, 5]} intensity={1.1} />
      <directionalLight position={[-3, 2, -4]} intensity={0.35} />
      <Suspense fallback={null}>
        <MarketGlbModel key={modelUrl} url={modelUrl} />
      </Suspense>
      <OrbitControls
        autoRotate={autoRotate}
        autoRotateSpeed={0.85}
        enablePan={false}
        enableZoom={false}
        minPolarAngle={Math.PI / 4}
        maxPolarAngle={Math.PI / 2.05}
        minDistance={2.2}
        maxDistance={6}
      />
    </>
  );
}

export function MarketModelViewer({ modelUrl, className = "" }: { modelUrl: string; className?: string }) {
  const reduceMotion = useReducedMotion();

  return (
    <div
      className={`relative h-[min(52vw,320px)] w-full touch-none sm:h-[380px] lg:h-[440px] ${className}`}
      aria-hidden
    >
      <Canvas
        className="!touch-none"
        dpr={[1, 1.75]}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        camera={{ position: [2.8, 1.4, 4.2], fov: 42, near: 0.1, far: 100 }}
        style={{ background: "transparent" }}
      >
        <Scene modelUrl={modelUrl} autoRotate={!reduceMotion} />
      </Canvas>
    </div>
  );
}

for (const market of HOME_MARKETS) {
  useGLTF.preload(market.modelUrl);
}
