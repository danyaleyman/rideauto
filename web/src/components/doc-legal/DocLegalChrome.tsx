/* eslint-disable @next/next/no-css-tags, @next/next/no-page-custom-font */
import type { ReactNode } from "react";

/** Общие стили юр. страниц. */
export function DocLegalChrome({ children }: { children: ReactNode }) {
  return (
    <>
      <link rel="stylesheet" href="/css/common.css" />
      <link
        href="https://fonts.googleapis.com/css2?family=Roboto:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap"
        rel="stylesheet"
      />
      <style>{`
        body { margin: 0; background: var(--wra-gray-100); font-family: var(--font-sans); color: var(--wra-gray-900); padding-bottom: 32px; }
        .doc-wrap { max-width: 980px; margin: 24px auto; padding: 0 16px; }
        .doc-card { background: var(--wra-surface); border: 1px solid var(--wra-border); border-radius: 16px; padding: clamp(20px, 4vw, 28px); }
        .doc-legal-page h1 { margin: 0 0 12px; font-size: clamp(1.35rem, 4vw, 1.75rem); line-height: 1.25; color: var(--wra-gray-900); }
        .doc-legal-page h2 { margin: 22px 0 8px; font-size: clamp(1rem, 2.5vw, 1.2rem); color: var(--wra-gray-900); }
        .doc-legal-page p, .doc-legal-page li { line-height: 1.6; color: var(--wra-gray-700); }
        .doc-legal-page .muted { color: var(--wra-text-muted); font-size: 14px; }
        .doc-legal-page .doc-card a { color: var(--wra-primary-dark); font-weight: 500; text-decoration: underline; text-underline-offset: 2px; }
        .legal-page { max-width: 980px; margin: 24px auto; background: var(--wra-surface); border: 1px solid var(--wra-border); border-radius: 16px; padding: clamp(20px, 4vw, 28px); }
        .legal-page h1 { margin: 0 0 14px; font-size: clamp(1.25rem, 3.5vw, 1.5rem); line-height: 1.3; color: var(--wra-gray-900); }
        .legal-page h2 { margin: 22px 0 10px; font-size: 1.05rem; color: var(--wra-gray-900); }
        .legal-page p, .legal-page li { line-height: 1.55; color: var(--wra-gray-700); }
        .legal-page ul { padding-left: 20px; }
        .legal-meta { font-size: 0.9rem; color: var(--wra-text-muted); margin-bottom: 14px; }
        .legal-back { margin-top: 22px; }
        .legal-page a { color: var(--wra-primary-dark); font-weight: 500; }
      `}</style>
      <div className="wra-page-gray doc-legal-page">{children}</div>
    </>
  );
}
