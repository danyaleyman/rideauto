/** Cookie name for app locale (set by middleware from `?lang=` or client `setLocale`). */
export const LOCALE_COOKIE = "WRA_LOCALE";

/** Локаль по умолчанию для статического/ISR-рендера (клиент корректирует из cookie). */
export const DEFAULT_LOCALE = "ru" as const;
