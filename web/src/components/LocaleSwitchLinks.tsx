"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

export function LocaleSwitchLinks({ className }: { className?: string }) {
  const pathname = usePathname();
  const sp = useSearchParams();

  function href(lang: "en" | "ru"): string {
    const p = new URLSearchParams(sp.toString());
    p.set("lang", lang);
    const q = p.toString();
    return q ? `${pathname}?${q}` : `${pathname}?lang=${lang}`;
  }

  return (
    <span className={className}>
      <Link href={href("en")} className="underline-offset-2 hover:underline" prefetch={false}>
        EN
      </Link>
      {" · "}
      <Link href={href("ru")} className="underline-offset-2 hover:underline" prefetch={false}>
        RU
      </Link>
    </span>
  );
}
