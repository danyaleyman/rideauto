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
  /* Статический каталог без API: перед catalog.js задайте window.WRA_ALLOW_CATALOG_JSON_FALLBACK = true (см. catalog allowCarsJsonFallback). */

  /** Публичный URL карточки: /detail/{id} (nginx отдаёт car.html). Фолбэк для старых ссылок — 301 на сервере. */
  window.wraCarDetailPath = function (id) {
    if (id == null || id === "") return "index.html";
    var s = String(id).trim();
    if (!s) return "index.html";
    return "/detail/" + encodeURIComponent(s);
  };
  window.wraCarDetailUrl = function (id) {
    var p = window.wraCarDetailPath(id);
    if (p === "index.html") {
      try {
        return new URL("index.html", window.location.href).href;
      } catch (e) {
        return "index.html";
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
