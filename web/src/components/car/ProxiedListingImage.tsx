"use client";

import Image from "next/image";
import { useProxiedCatalogThumbUrls } from "@/lib/catalog-image-proxy";

type Props = {
  src: string;
  alt: string;
  width: number;
  height: number;
  sizes: string;
  className?: string;
};

/** Превью в сетке (похожие / подборки): Che168 CDN через /api/images. */
export function ProxiedListingImage({ src, alt, width, height, sizes, className }: Props) {
  const urls = useProxiedCatalogThumbUrls(src.trim() ? [src.trim()] : []);
  const u = urls[0] ?? src;
  return (
    <Image
      src={u || src}
      alt={alt}
      width={width}
      height={height}
      sizes={sizes}
      className={className}
      loading="lazy"
      decoding="async"
      unoptimized
    />
  );
}
