/**
 * Продакшен: укажите username бота для Telegram Login (без @).
 * В @BotFather → ваш бот → поле username. Домен сайта добавьте в настройках бота (Login Domain).
 */
(function () {
  if (typeof window.WRA_TELEGRAM_LOGIN_BOT !== "string" || !window.WRA_TELEGRAM_LOGIN_BOT.trim()) {
    window.WRA_TELEGRAM_LOGIN_BOT = "rideauto_bot";
  }
  /* Пустая строка = запросы к API с того же origin (/api/...). Иначе полный URL API, например https://rideauto.ru */
  if (typeof window.WRA_API_BASE !== "string") {
    window.WRA_API_BASE = "";
  }
  /* Синхронизируйте с query ?v= у car-page*.js в car.html при релизе (или scripts/bump-asset-version.mjs). */
  if (typeof window.WRA_ASSET_VERSION !== "string" || !window.WRA_ASSET_VERSION.trim()) {
    window.WRA_ASSET_VERSION = "20260405car";
  }
  /* Статический каталог без API: перед catalog.js задайте window.WRA_ALLOW_CATALOG_JSON_FALLBACK = true (см. catalog allowCarsJsonFallback). */
  /* Таймаут fetch /api/cars (мс). По умолчанию 180000 в catalog.js; при очень тяжёлой БД можно поднять, задав число до подключения catalog.js. */
  /* if (typeof window.WRA_CATALOG_CARS_TIMEOUT_MS !== "number") { window.WRA_CATALOG_CARS_TIMEOUT_MS = 240000; } */

  /** Публичный URL карточки: /detail/{id} (nginx отдаёт car.html). Фолбэк для старых ссылок — 301 на сервере. */
  window.wraCarDetailPath = function (id) {
    if (id == null || id === "") return "/";
    var s = String(id).trim();
    if (!s) return "/";
    return "/detail/" + encodeURIComponent(s);
  };
  window.wraCarDetailUrl = function (id) {
    var p = window.wraCarDetailPath(id);
    if (p === "/") {
      try {
        return new URL("/", window.location.origin).href;
      } catch (e) {
        return "/";
      }
    }
    try {
      return new URL(p, window.location.origin + "/").href;
    } catch (e2) {
      return p;
    }
  };

  (function preconnectApiOrigin() {
    var raw = window.WRA_API_BASE;
    if (typeof raw !== "string" || !raw.trim()) return;
    try {
      var u = new URL(raw, window.location.href);
      if (u.origin === window.location.origin) return;
      if (document.querySelector('link[rel="preconnect"][href="' + u.origin + '"]')) return;
      var l = document.createElement("link");
      l.rel = "preconnect";
      l.href = u.origin;
      l.crossOrigin = "anonymous";
      document.head.appendChild(l);
    } catch (e) {}
  })();
})();
