import type { ReactNode } from "react";

/** Без SiteShell: страница «Как купить» — полноэкранный iframe с собственной вёрсткой. */
export default function StandaloneLayout({ children }: { children: ReactNode }) {
  return children;
}
