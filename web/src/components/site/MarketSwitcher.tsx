"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const KOREA_HREF = "/catalog?region=korea&source=encar";
const CHINA_HREF = "/catalog?region=china&source=china";

export function MarketSwitcher() {
  const pathname = usePathname();
  const sp = useSearchParams();

  const onCatalog = pathname === "/catalog";
  const region = (sp.get("region") || "").toLowerCase();
  const source = (sp.get("source") || "").toLowerCase();
  const isChina =
    region === "china" ||
    source === "china" ||
    source === "dongchedi" ||
    source === "che168";
  const koreaActive = onCatalog && !isChina;
  const chinaActive = onCatalog && isChina;

  return (
    <div className="border-b border-border bg-muted/40">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-center gap-2 px-4 py-2 sm:justify-between">
        <p className="text-xs font-medium text-muted-foreground sm:text-sm">Выбор рынка</p>
        <div className="flex items-center gap-1.5">
          <Button
            variant={koreaActive ? "default" : "outline"}
            size="sm"
            className={cn("rounded-full px-4", !koreaActive && "bg-background")}
            asChild
          >
            <Link href={KOREA_HREF} prefetch={false}>
              Корея
            </Link>
          </Button>
          <Button
            variant={chinaActive ? "default" : "outline"}
            size="sm"
            className={cn("rounded-full px-4", !chinaActive && "bg-background")}
            asChild
          >
            <Link href={CHINA_HREF} prefetch={false}>
              Китай
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
