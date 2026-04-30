"use client";

export type CookieConsent = {
  necessary: true;
  analytics: boolean;
  marketing: boolean;
  updatedAt: string;
};

export const COOKIE_CONSENT_STORAGE_KEY = "wra-cookie-consent-v1";
export const COOKIE_CONSENT_EVENT = "wra-cookie-consent-changed";
export const COOKIE_CONSENT_OPEN_EVENT = "wra-cookie-consent-open";

export function readCookieConsent(): CookieConsent | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(COOKIE_CONSENT_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<CookieConsent>;
    if (typeof parsed?.analytics !== "boolean") return null;
    if (typeof parsed?.marketing !== "boolean") return null;
    return {
      necessary: true,
      analytics: parsed.analytics,
      marketing: parsed.marketing,
      updatedAt: typeof parsed.updatedAt === "string" ? parsed.updatedAt : new Date().toISOString(),
    };
  } catch {
    return null;
  }
}

export function writeCookieConsent(consent: Omit<CookieConsent, "necessary" | "updatedAt">): CookieConsent {
  const next: CookieConsent = {
    necessary: true,
    analytics: consent.analytics,
    marketing: consent.marketing,
    updatedAt: new Date().toISOString(),
  };
  if (typeof window !== "undefined") {
    localStorage.setItem(COOKIE_CONSENT_STORAGE_KEY, JSON.stringify(next));
    window.dispatchEvent(new CustomEvent(COOKIE_CONSENT_EVENT, { detail: next }));
  }
  return next;
}
