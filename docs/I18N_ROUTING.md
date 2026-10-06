# i18n: текущее состояние и маршруты

## Сейчас

- Тексты: `web/messages/ru.json`, `web/messages/en.json`.
- **Локаль:** cookie `WRA_LOCALE` (`ru` | `en`).
- **URL:**
  - Prefixed: `/en/...`, `/ru/...` (middleware rewrite на существующие `(site)` / `car` маршруты).
  - Query: `?lang=en` / `?lang=ru` (ставит cookie).
  - Первый визит без cookie: `Accept-Language` (только bootstrap).
- Серверные компоненты: `getServerLocale()` из `web/src/lib/locale-server.ts`.
- Клиент: `LocaleProvider` + `useLocaleContext()` (`t`, `setLocale`).
- Форматы: `web/src/lib/format-locale.ts`.
- **SEO / hreflang:** `generateMetadata` + `alternates.languages` для `ru-RU` / `en-US` (path с префиксом или `?lang=`).

## Паритет сообщений

```bash
cd web && node scripts/i18n-key-parity.mjs
```

## Favorites

Избранное — для аутентифицированных пользователей (API). Анонимам показывается CTA «войти» (`favorites.loginRequired` / `header.favoritesLoginHint`), не мёртвая кнопка.

## Как проверить

- `https://…/en/catalog` и `https://…/ru/catalog` → 200, язык sticky по cookie.
- `?lang=en` затем навигация без query сохраняет EN.
