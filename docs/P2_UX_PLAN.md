# P2 UX — план реализации

Цель: закрыть утечки воронки **поиск → каталог → карточка → заявка**, не ломая i18n / Meili / URL-фильтры и не делая пиксельный редизайн.

| Phase | Фокус | Статус | AC |
|-------|--------|--------|-----|
| **1** | Mobile lead parity | Done | Sticky CTA → QuickBuy (+ contacts secondary) |
| **2** | Listing card hit-area | Done | Одна overlay-ссылка на всю карточку; actions z-2 |
| **3** | Shared lead PD block | Done | `LeadPdAgreeField` для QuickBuy + `/buy` |
| **4** | Browse friction | Done | Clear search (X / Escape) в toolbar |
| **5** | Car CTA hierarchy | Done | Primary buy на sidebar + sticky |
| **6** | Storybook quality | Done | Stories: QuickBuy, ListingCard, ResultsToolbar, PdAgree; `npm run build-storybook` |

Не делаем в P2: новый визуальный бренд, virtual list, смена facet schema.

Локально: `cd web && npm run storybook`
