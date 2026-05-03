/** Общая геометрия страниц с шапкой SiteShell: каталог, карточка и др. */

export const siteMainSurfaceClass =
  "min-h-screen overflow-x-hidden bg-gradient-to-b from-muted/40 via-background to-background pt-2 sm:pt-4";

/** Нижний отступ: у карточки больше из‑за мобильной sticky-плашки. */
export const siteMainBottomCatalogClass = "pb-12 sm:pb-16";
export const siteMainBottomCarClass = "pb-32 sm:pb-16 lg:pb-14";

export const siteContainerClass = "relative mx-auto min-w-0 max-w-[1440px] px-3 sm:px-6 lg:px-10";

export const siteBreadcrumbBarClass =
  "mb-5 flex min-w-0 rounded-2xl border border-border/50 bg-card/70 px-3 py-3 shadow-sm backdrop-blur-sm sm:mb-6 sm:px-5";
