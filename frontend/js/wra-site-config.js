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
})();
