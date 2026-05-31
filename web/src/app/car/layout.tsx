import type { ReactNode } from "react";
import { SiteShell } from "@/components/SiteShell";

// Без generateMetadata с headers() — иначе /car форсится в dynamic-рендер.
// Канонический URL и hreflang задаются статически в car/[ref]/page.tsx (buildCarMetadata).
export default function CarLayout({ children }: { children: ReactNode }) {
  return <SiteShell>{children}</SiteShell>;
}
