/* eslint-disable @next/next/no-css-tags, @next/next/no-page-custom-font */
import fs from "node:fs";
import path from "node:path";
import { LegacyMarketingScripts } from "@/components/legacy-marketing/LegacyMarketingScripts";

type Props = {
  slug: "about" | "contacts";
  /** Обёртка как `.contacts-wrap` для корректной вёрстки */
  wrapClassName?: string;
};

function readFileSafe(filePath: string): string {
  try {
    return fs.readFileSync(filePath, "utf8");
  } catch {
    return "";
  }
}

export function LegacyMarketingPage({ slug, wrapClassName }: Props) {
  const base = path.join(process.cwd(), "src", "legacy", "marketing", slug);
  const style = readFileSafe(path.join(base, "styles.css"));
  const main = readFileSafe(path.join(base, "main.html"));
  if (!style || !main) {
    throw new Error(
      `Нет фрагментов marketing/${slug} — выполните npm run sync-legacy в web/`,
    );
  }

  const block = wrapClassName ? (
    <div className={wrapClassName} dangerouslySetInnerHTML={{ __html: main }} />
  ) : (
    <div dangerouslySetInnerHTML={{ __html: main }} />
  );

  return (
    <>
      <link rel="stylesheet" href="/css/common.css?v=20260410" />
      <link rel="stylesheet" href="/css/auth-favorites.css?v=20260410" />
      <link rel="stylesheet" href="/css/cookie-consent.css?v=20260410" />
      <link
        rel="stylesheet"
        href="https://fonts.googleapis.com/css2?family=Roboto:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap"
      />
      <link
        rel="stylesheet"
        href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"
        crossOrigin="anonymous"
      />
      <script defer src="/js/wra-site-config.js?v=20260421" />
      <script defer src="/js/copy-protection.js?v=20260410" />
      <script defer src="/js/auth-favorites.js?v=20260406" />
      <style dangerouslySetInnerHTML={{ __html: style }} />
      {block}
      <LegacyMarketingScripts />
    </>
  );
}
