import type { ReactNode } from "react";
import {
  siteContainerClass,
  siteMainBottomCatalogClass,
  siteMainSurfaceClass,
} from "@/lib/site-layout";

/** Статичная оболочка каталога (RSC): фон, контейнер, место под интерактивный слой. */
export function CatalogPageLayout({ children }: { children: ReactNode }) {
  return (
    <div className={`${siteMainSurfaceClass} ${siteMainBottomCatalogClass}`}>
      <div className={siteContainerClass}>{children}</div>
    </div>
  );
}
