/**
 * Флаги через env (``NEXT_PUBLIC_*`` вшиваются при сборке).
 * Для Docker/прода: задайте в .env и пересоберите ``web``.
 */
export const featureFlags = {
  /** Блок доверия на главной (отключить: ``NEXT_PUBLIC_FEATURE_HOME_TRUST=0``). */
  showHomeTrustStrip: process.env.NEXT_PUBLIC_FEATURE_HOME_TRUST !== "0",
  /** Виртуализация списка (@tanstack/react-virtual) при длинной выдаче. По умолчанию включена; ``=0`` отключает. */
  enableCatalogVirtualList: process.env.NEXT_PUBLIC_FEATURE_VIRTUAL_LIST !== "0",
  /** Минимум карточек на странице, чтобы включить virtual list (см. PER_PAGE). */
  catalogVirtualListMinItems: 8,
} as const;
