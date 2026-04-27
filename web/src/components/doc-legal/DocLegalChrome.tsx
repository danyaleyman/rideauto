"use client";

import type { ReactNode } from "react";
import { MotionFadeUp } from "@/components/ui/motion";

/** Общие стили юр. страниц. */
export function DocLegalChrome({ children }: { children: ReactNode }) {
  return (
    <>
      <style>{`
        body { margin: 0; background: #f4f4f5; font-family: Arial, Helvetica, sans-serif; color: #111827; padding-bottom: 32px; }
        .doc-wrap { max-width: 980px; margin: 24px auto; padding: 0 16px; }
        .doc-card { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px; padding: clamp(20px, 4vw, 28px); }
        .doc-legal-page h1 { margin: 0 0 12px; font-size: clamp(1.35rem, 4vw, 1.75rem); line-height: 1.25; color: #111827; }
        .doc-legal-page h2 { margin: 22px 0 8px; font-size: clamp(1rem, 2.5vw, 1.2rem); color: #111827; }
        .doc-legal-page p, .doc-legal-page li { line-height: 1.6; color: #374151; }
        .doc-legal-page .muted { color: #6b7280; font-size: 14px; }
        .doc-legal-page .doc-card a { color: #1d4ed8; font-weight: 500; text-decoration: underline; text-underline-offset: 2px; }
        .legal-page { max-width: 980px; margin: 24px auto; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px; padding: clamp(20px, 4vw, 28px); }
        .legal-page h1 { margin: 0 0 14px; font-size: clamp(1.25rem, 3.5vw, 1.5rem); line-height: 1.3; color: #111827; }
        .legal-page h2 { margin: 22px 0 10px; font-size: 1.05rem; color: #111827; }
        .legal-page p, .legal-page li { line-height: 1.55; color: #374151; }
        .legal-page ul { padding-left: 20px; }
        .legal-meta { font-size: 0.9rem; color: #6b7280; margin-bottom: 14px; }
        .legal-back { margin-top: 22px; }
        .legal-page a { color: #1d4ed8; font-weight: 500; }
      `}</style>
      <MotionFadeUp className="wra-page-gray doc-legal-page">{children}</MotionFadeUp>
    </>
  );
}
