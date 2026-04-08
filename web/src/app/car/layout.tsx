import type { ReactNode } from "react";
import { SiteShell } from "@/components/SiteShell";

export default function CarLayout({ children }: { children: ReactNode }) {
  return <SiteShell>{children}</SiteShell>;
}
