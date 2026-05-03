/**
 * Флаги через env (``NEXT_PUBLIC_*`` вшиваются при сборке).
 * Для Docker/прода: задайте в .env и пересоберите ``web``.
 */
export const featureFlags = {
  /** Блок доверия на главной (отключить: ``NEXT_PUBLIC_FEATURE_HOME_TRUST=0``). */
  showHomeTrustStrip: process.env.NEXT_PUBLIC_FEATURE_HOME_TRUST !== "0",
  /** Зарезервировано: виртуализация списка при очень длинной выдаче. */
  enableCatalogVirtualList: process.env.NEXT_PUBLIC_FEATURE_VIRTUAL_LIST === "1",
} as const;
