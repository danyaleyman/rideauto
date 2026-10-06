# ADR 0002: Hybrid scrape resilience (не full-browser / не SeleniumBase)

- **Статус:** принято  
- **Дата:** 2026-10-06  

## Контекст

Прямые HTTP-клиенты (`aiohttp`/`requests`) легко отличаются по TLS (JA3) и поведению. Готовые стеки вроде SeleniumBase UC Mode решают *browser bot-score*, но гонять весь каталог через Chromium в 10–50× дороже и менее стабильно. В RideAuto уже был правильный зародыш гибрида (Che168: Playwright bootstrap → sticky cookies → aiohttp).

## Решение

Внутренняя **Scraper Resilience Platform** (`backend/scraper_pipeline/resilience/`):

1. **Transport** — `curl_cffi` с Chrome impersonate как hot-path HTTP (TLS как у браузера); `aiohttp` только как fallback.
2. **BrowserProfile** — один Chrome major для UA + `sec-ch-ua` + impersonate (без ротации Firefox/Safari поверх Chrome TLS).
3. **SessionProvider (Playwright)** — браузер только как фабрика сессии (куки / challenge page / sticky egress), не как scraper каталога.
4. **ResiliencePolicy** — эскалация session refresh, adaptive concurrency, jitter degrade.
5. **Challenge handlers (Phase 4)** — только детекция + deferred error до зафиксированного инцидента; без превентивных CAPTCHA-solver'ов.

Не вводим второй браузерный рантайм (SeleniumBase) рядом с Playwright.

## Последствия

- Новый источник = адаптер + профиль + опциональный SessionProvider, без копипасты клиента.
- Ops: `python backend/scripts/resilience_probes.py --source che168|encar`.
- Метрики: `scraper_transport_impersonateinfo`, `scraper_session_*`, `scraper_challenge_detected_total`, `scraper_policy_*`.
- Если probe покажет challenge, который vanilla Playwright не проходит — тогда точечно рассматривать stealth-форк / headful, а не переписывать пайплайн на full-browser.
