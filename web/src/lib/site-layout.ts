/** Общая геометрия страниц с шапкой SiteShell: каталог, карточка и др. */

/**
 * Плоский фон без градиента: контент читается на нейтральной поверхности.
 * `overflow-x-clip` (а не `hidden`) — чтобы обёртка не становилась scroll-контейнером
 * и sticky-элементы внутри (мобильная панель фильтров, тулбар) липли к окну, а не к ней.
 */
export const siteMainSurfaceClass = "min-h-screen overflow-x-clip bg-background pt-3 sm:pt-5";

/**
 * Нижний отступ каталога: на мобиле добавляем запас под bottom tab bar (~3.25rem)
 * + safe-area. На sm+ — обычный отступ.
 */
export const siteMainBottomCatalogClass =
  "pb-[calc(4.5rem+env(safe-area-inset-bottom))] sm:pb-16";

/** Запас под sticky CTA + bottom tab bar + safe-area + cookie-баннер. */
export const siteMainBottomCarClass =
  "pb-[calc(9.5rem+env(safe-area-inset-bottom)+var(--wra-cookie-banner-height,0px))] sm:pb-[calc(6.5rem+env(safe-area-inset-bottom)+var(--wra-cookie-banner-height,0px))] lg:pb-14";

export const siteContainerClass = "relative mx-auto min-w-0 max-w-[1440px] px-3 sm:px-6 lg:px-10";

/** Хлебные крошки: обычная строка текста, без контейнера. */
export const siteBreadcrumbBarClass = "mb-4 flex min-w-0 items-center text-sm sm:mb-5";
