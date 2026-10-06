# ADR 0005: Challenge escalation L0–L3 (no CAPTCHA farms)

- **Статус:** принято  
- **Дата:** 2026-10-06  

## Контекст

Hard WAF/CAPTCHA оставался «deferred error». Нужен управляемый автопуть без внешних solver’ов.

## Решение

Уровни в `scraper_pipeline.resilience.challenge`:

| Level | Action |
|-------|--------|
| L0 | HTTP impersonate retry |
| L1 | Playwright session refresh (headless) |
| L2 | Headful Playwright refresh |
| L3 | Cookie inject from `WRA_COOKIE_INJECT_PATH` JSON |
| Human | `ChallengeNeedsHumanError` → ops |

`WRA_CHALLENGE_MAX_LEVEL` (default 3) caps auto escalation.

## Не делаем

- Платные CAPTCHA farms / bypass-as-a-service в репозитории.

## Последствия

- Workers/ops могут звать `escalate_che168_session(..., level=L1|L2|L3)`.
- Human path остаётся для rare hard CAPTCHA — не «дыра», а явный terminal state с playbook.
