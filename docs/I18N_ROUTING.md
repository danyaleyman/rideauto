# i18n: текущее состояние и маршруты

## Сейчас

- Тексты: `web/messages/ru.json`, `web/messages/en.json`.
- **Локаль:** cookie `WRA_LOCALE` (`ru` | `en`), выставляется query-параметром **`?lang=en`** или **`?lang=ru`** (см. `web/src/middleware.ts`).
- Серверные компоненты: `getServerLocale()` из `web/src/lib/locale-server.ts`.
- Клиент: `LocaleProvider` + `useLocaleContext()` (`t`, `setLocale`).
- Форматы дат/чисел/валюты: `web/src/lib/format-locale.ts`.

## Не сделано (как у «больших» продуктов)

- Отдельные URL вида `/en/catalog` без полной реструктуризации `app/[locale]/…` не вводились.
- Нет автоопределения только из `Accept-Language` без явного `?lang=` (можно добавить в middleware при необходимости).

## Как включить английский для проверки

Откройте любую страницу с `?lang=en`, затем навигация сохранит cookie.
