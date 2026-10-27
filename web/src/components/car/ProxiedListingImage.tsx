"use client";

import Image from "next/image";
import { useLocaleContext } from "@/components/LocaleProvider";
import { catalogImageNeedsProxy, useProxiedCatalogThumbUrls } from "@/lib/catalog-image-proxy";
import { cn } from "@/lib/utils";

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
  const { t } = useLocaleContext();
  const srcTrimmed = src.trim();
  const urls = useProxiedCatalogThumbUrls(srcTrimmed ? [srcTrimmed] : []);
  const u = urls[0] ?? "";
  if (!srcTrimmed) {
    return (
      <div
        className={cn("flex items-center justify-center bg-muted text-xs text-muted-foreground", className)}
        role="img"
        aria-label={alt}
      >
        {t("common.noPhoto")}
      </div>
    );
  }
  if (catalogImageNeedsProxy(srcTrimmed) && !u) {
    return (
      <div
        className={cn("animate-pulse bg-muted/80", className)}
        role="img"
        aria-label={`${t("common.loading")}: ${alt}`}
      />
    );
  }
  return (
    <Image
      src={u || srcTrimmed}
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
