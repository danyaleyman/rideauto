import type { Metadata } from "next";
import type { ReactNode } from "react";
import { SiteShell } from "@/components/SiteShell";
import { localeAlternatesMetadata } from "@/lib/site-alternates-metadata";

export async function generateMetadata(): Promise<Metadata> {
  return { ...(await localeAlternatesMetadata()) };
}

export default function CarLayout({ children }: { children: ReactNode }) {
  return <SiteShell>{children}</SiteShell>;
}
