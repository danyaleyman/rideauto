  (function() {
    const PER_PAGE = 12;
    let page = 1;
    let pageCars = [];
    let catalogTotal = 0;
    let catalogPages = 1;
    let catalogRequestId = 0;
    /** Отмена предыдущего запроса списка при быстрой смене фильтров/страницы. */
    let carsListAbort = null;
    /** Отмена предыдущего /api/facets, чтобы не ждать ответ по устаревшим параметрам. */
    let facetsListAbort = null;
    let useStaticCatalog = false;
    let staticCatalogCache = null;
    const API_BASE = (typeof window.WRA_API_BASE === 'string' ? window.WRA_API_BASE : '').replace(/\/+$/, '');
    /**
     * Рынок: Корея → `source=encar`. Китай: `?region=china` → `source=china` (Dongchedi в отдельной БД);
     * узко — `?source=dongchedi`; старые ссылки `?source=che168` трактуются как китайский каталог (`source=china`).
     * `window.WRA_CATALOG_SOURCE` — только если в URL нет `region`/`source` (иначе вкладка Китай даст Корею).
     */
    var CATALOG_REGION = 'korea';
    let CATALOG_SOURCE = 'encar';

    /** Перед каждым API-запросом: рынок только из URL (и фолбэк WRA_*), иначе легко запросить Корею при ?region=china. */
    function syncCatalogMarketFromLocation() {
      try {
        var sp = new URLSearchParams(window.location.search || '');
        var srcQ = (sp.get('source') || '').toLowerCase();
        var reg = (sp.get('region') || '').toLowerCase();
        var regionChina = reg === 'china';
        var regionKorea = reg === 'korea';

        if (regionChina || srcQ === 'che168' || srcQ === 'dongchedi' || srcQ === 'china') {
          CATALOG_REGION = 'china';
          if (srcQ === 'dongchedi') CATALOG_SOURCE = 'dongchedi';
          else CATALOG_SOURCE = 'china';
          return;
        }
        if (regionKorea) {
          CATALOG_REGION = 'korea';
          CATALOG_SOURCE = 'encar';
          return;
        }

        var w = typeof window !== 'undefined' && window.WRA_CATALOG_SOURCE ? String(window.WRA_CATALOG_SOURCE).trim() : '';
        if (w) {
          var wl = w.toLowerCase();
          if (wl === 'che168' || wl === 'dongchedi' || wl === 'china') {
            CATALOG_REGION = 'china';
            CATALOG_SOURCE = wl === 'dongchedi' ? 'dongchedi' : 'china';
            return;
          }
          CATALOG_SOURCE = w;
          CATALOG_REGION = 'korea';
          return;
        }
        CATALOG_REGION = 'korea';
        CATALOG_SOURCE = 'encar';
      } catch (e) {
        CATALOG_REGION = 'korea';
        CATALOG_SOURCE = 'encar';
      }
    }

    function applyCatalogRegionUi() {
      try {
        var h1 = document.querySelector('.catalog-header h1');
        if (h1) {
          h1.textContent =
            CATALOG_REGION === 'china' ? 'Автомобили из Китая' : 'Автомобили из Кореи';
        }
        var hintNew = document.querySelector('.sort-option[data-value="date_new"] .sort-option-hint');
        if (hintNew && CATALOG_REGION === 'china') {
          hintNew.textContent = 'по дате в каталоге';
        }
      } catch (e) { /* ignore */ }
    }

    syncCatalogMarketFromLocation();
    applyCatalogRegionUi();
    /** Таймаут ответа списка (мс); при медленном API не держим браузер в вечном pending. */
    var CATALOG_CARS_TIMEOUT_MS =
      typeof window.WRA_CATALOG_CARS_TIMEOUT_MS === 'number' && window.WRA_CATALOG_CARS_TIMEOUT_MS > 5000
        ? window.WRA_CATALOG_CARS_TIMEOUT_MS
        : 300000;
    var CATALOG_STATS_TIMEOUT_MS =
      typeof window.WRA_CATALOG_STATS_TIMEOUT_MS === 'number' && window.WRA_CATALOG_STATS_TIMEOUT_MS > 3000
        ? window.WRA_CATALOG_STATS_TIMEOUT_MS
        : 90000;
    function apiUrl(path) {
      return API_BASE + path;
    }

    /**
     * Каталог не кладём в HTTP disk/memory cache: при 200 с пустым result после сбоя API
     * страница «залипает» на 0 объявлений, пока не истечёт max-age (см. Cache-Control с бэкенда).
     */
    function catalogApiFetchInit(extra) {
      var o = extra && typeof extra === 'object' ? Object.assign({}, extra) : {};
      if (!('cache' in o)) o.cache = 'no-store';
      return o;
    }

    function withTimeout(promise, ms, label) {
      if (!ms || ms <= 0) return promise;
      return Promise.race([
        promise,
        new Promise(function(_, reject) {
          setTimeout(function() {
            reject(new Error(label || 'timeout'));
          }, ms);
        }),
      ]);
    }

    function showCatalogErrorBanner(message) {
      if (!gridEl) return;
      gridEl.setAttribute('aria-busy', 'false');
      var esc = (typeof message === 'string' ? message : '').replace(/</g, '&lt;').replace(/"/g, '&quot;');
      var sub =
        '<p style="margin:12px 0 0;font-size:0.875rem;color:var(--wra-text-muted);">Если проблема не проходит, проверьте <code>/api/health</code> и нагрузку на сервер.</p>';
      gridEl.innerHTML =
        '<div class="catalog-error-banner" style="grid-column:1/-1;text-align:center;padding:40px;background:var(--wra-surface);border-radius:24px;border:1px solid var(--wra-border);">' +
        '<p style="margin:0 0 16px;">' +
        (esc || 'Не удалось загрузить каталог.') +
        '</p>' +
        sub +
        '<div style="margin-top:20px;display:flex;gap:12px;justify-content:center;flex-wrap:wrap;">' +
        '<button type="button" class="btn btn-primary" id="wraCatalogRetryBtn">Повторить</button>' +
        '<a href="/catalog" class="btn btn-secondary">Обновить страницу</a>' +
        '</div></div>';
      var btn = document.getElementById('wraCatalogRetryBtn');
      if (btn) {
        btn.addEventListener('click', function() {
          window.location.reload();
        });
      }
    }
    /**
     * Фолбэк: скачать целиком cars.json в браузер. На проде при ~100k+ машин это гигабайты → OOM и «Aw Snap».
     * По умолчанию разрешён только если API на другом origin (WRA_API_BASE не пустой): тогда локальный cars.json часто маленький снапшот.
     * Чисто статический каталог без API: задайте window.WRA_ALLOW_CATALOG_JSON_FALLBACK = true до catalog.js (и держите выгрузку небольшой или задайте лимит).
     */
    function allowCarsJsonFallback() {
      if (CATALOG_REGION === 'china')
        return false;
      if (typeof window.WRA_ALLOW_CATALOG_JSON_FALLBACK === 'boolean') {
        return window.WRA_ALLOW_CATALOG_JSON_FALLBACK;
      }
      return API_BASE !== '';
    }
    var CATALOG_JSON_FALLBACK_MAX_BYTES =
      typeof window.WRA_CATALOG_JSON_FALLBACK_MAX_BYTES === 'number' && window.WRA_CATALOG_JSON_FALLBACK_MAX_BYTES > 0
        ? window.WRA_CATALOG_JSON_FALLBACK_MAX_BYTES
        : 40 * 1024 * 1024;

    // DOM элементы
    const gridEl = document.getElementById('grid');
    const paginationEl = document.getElementById('pagination');
    const foundCounter = document.getElementById('foundCounter');
    const filterCountEl = document.getElementById('filterCount');
    const markListEl = document.getElementById('markList');
    const modelListEl = document.getElementById('modelList');
    const generationListEl = document.getElementById('generationList');
    const trimListEl = document.getElementById('trimList');
    const markTrigger = document.getElementById('markTrigger');
    const markPanel = document.getElementById('markPanel');
    const modelTrigger = document.getElementById('modelTrigger');
    const modelPanel = document.getElementById('modelPanel');
    const generationTrigger = document.getElementById('generationTrigger');
    const generationPanel = document.getElementById('generationPanel');
    const trimTrigger = document.getElementById('trimTrigger');
    const trimPanel = document.getElementById('trimPanel');
    const sortTrigger = document.getElementById('sortTrigger');
    const sortPanel = document.getElementById('sortPanel');
    const sortOptionsEl = document.getElementById('sortOptions');
    const yearFromTrigger = document.getElementById('yearFromTrigger');
    const yearFromPanel = document.getElementById('yearFromPanel');
    const yearFromOptions = document.getElementById('yearFromOptions');
    const monthFromTrigger = document.getElementById('monthFromTrigger');
    const monthFromPanel = document.getElementById('monthFromPanel');
    const monthFromOptions = document.getElementById('monthFromOptions');
    const yearToTrigger = document.getElementById('yearToTrigger');
    const yearToPanel = document.getElementById('yearToPanel');
    const yearToOptions = document.getElementById('yearToOptions');
    const monthToTrigger = document.getElementById('monthToTrigger');
    const monthToPanel = document.getElementById('monthToPanel');
    const monthToOptions = document.getElementById('monthToOptions');
    const sortSelect = document.getElementById('sortSelect');
    const catalogAriaLive = document.getElementById('catalogAriaLive');
    const filtersOpenBtn = document.getElementById('filtersOpenBtn');
    const filtersDrawerOverlay = document.getElementById('filtersDrawerOverlay');
    const filtersDrawerClose = document.getElementById('filtersDrawerClose');
    const filtersBadge = document.getElementById('filtersBadge');

    const CASCADE_DROPDOWN_PAIRS = [
      [markTrigger, markPanel],
      [modelTrigger, modelPanel],
      [generationTrigger, generationPanel],
      [trimTrigger, trimPanel]
    ];
    var cascadeFloatRepositionRaf = null;
    function undockAllCascadePanels() {
      CASCADE_DROPDOWN_PAIRS.forEach(function(pair) {
        var panel = pair[1];
        if (!panel) return;
        panel.classList.remove('filter-dropdown-panel--floating');
        ['--wra-float-left', '--wra-float-top', '--wra-float-width', '--wra-float-max-height'].forEach(function(prop) {
          panel.style.removeProperty(prop);
        });
      });
    }
    function dockOpenCascadePanel(trigger, panel) {
      if (!trigger || !panel || !panel.classList.contains('is-open') || trigger.disabled) return;
      var r = trigger.getBoundingClientRect();
      var gap = 4;
      var top = r.bottom + gap;
      var maxH = Math.min(260, Math.max(120, window.innerHeight - top - 8));
      panel.classList.add('filter-dropdown-panel--floating');
      /* Округление — меньше субпиксельного дрожания при частых пересчётах. */
      panel.style.setProperty('--wra-float-left', Math.round(r.left) + 'px');
      panel.style.setProperty('--wra-float-top', Math.round(top) + 'px');
      panel.style.setProperty('--wra-float-width', Math.max(1, Math.round(r.width)) + 'px');
      panel.style.setProperty('--wra-float-max-height', Math.round(maxH) + 'px');
    }
    /** Один пересчёт на кадр + игнор скролла внутри открытой панели (не дергать fixed-блок без нужды). */
    function scheduleRepositionOpenCascadePanels(ev) {
      var t = ev && ev.target;
      if (t && typeof t.closest === 'function' && t.closest('.filter-dropdown-panel')) return;
      if (cascadeFloatRepositionRaf != null) return;
      cascadeFloatRepositionRaf = requestAnimationFrame(function() {
        cascadeFloatRepositionRaf = null;
        CASCADE_DROPDOWN_PAIRS.forEach(function(pair) {
          if (pair[1] && pair[1].classList.contains('is-open')) dockOpenCascadePanel(pair[0], pair[1]);
        });
      });
    }

    function showSkeleton() {
      if (!gridEl) return;
      gridEl.setAttribute('aria-busy', 'true');
      var html = '';
      for (var i = 0; i < 6; i++) {
        html += '<div class="skeleton-card"><div class="skeleton-preview"></div><div class="skeleton-body"><div class="skeleton-line wide"></div><div class="skeleton-line narrow"></div><div class="skeleton-line narrow"></div><div class="skeleton-line wide"></div></div></div>';
      }
      gridEl.innerHTML = html;
    }

    function closeFiltersDrawer() {
      if (filtersDrawerOverlay) filtersDrawerOverlay.classList.remove('is-open');
      if (filtersOpenBtn) filtersOpenBtn.setAttribute('aria-expanded', 'false');
      document.body.classList.remove('filters-drawer-open');
    }
    function openFiltersDrawer() {
      if (filtersDrawerOverlay) filtersDrawerOverlay.classList.add('is-open');
      if (filtersOpenBtn) filtersOpenBtn.setAttribute('aria-expanded', 'true');
      document.body.classList.add('filters-drawer-open');
      if (markListEl && !markListEl.querySelector('input[type=checkbox]')) {
        scheduleFacetRefresh(catalogRequestId, true);
      }
    }
    if (filtersOpenBtn && filtersDrawerOverlay) {
      filtersOpenBtn.addEventListener('click', openFiltersDrawer);
      filtersDrawerOverlay.addEventListener('click', closeFiltersDrawer);
    }
    if (filtersDrawerClose) filtersDrawerClose.addEventListener('click', closeFiltersDrawer);

    function closeAllDropdowns() {
      undockAllCascadePanels();
      [markPanel, modelPanel, generationPanel, trimPanel, sortPanel, yearFromPanel, monthFromPanel, yearToPanel, monthToPanel].forEach(function(p) {
        if (p) { p.classList.remove('is-open'); }
      });
      [markTrigger, modelTrigger, generationTrigger, trimTrigger, sortTrigger, yearFromTrigger, monthFromTrigger, yearToTrigger, monthToTrigger].forEach(function(b) {
        if (b) {
          b.classList.remove('active');
          b.setAttribute('aria-expanded', 'false');
        }
      });
    }
    function syncCustomSelectUi(selectEl, triggerEl, optionsEl, fallbackText) {
      if (!selectEl || !triggerEl || !optionsEl) return;
      const opts = Array.from(selectEl.options || []);
      optionsEl.innerHTML = '';
      let selectedText = fallbackText || '';
      opts.forEach(function(opt) {
        if (opt.value === '') return;
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'sort-option';
        btn.setAttribute('data-value', opt.value);
        btn.textContent = (opt.textContent || '').trim();
        if (opt.value === selectEl.value) {
          btn.classList.add('active');
          selectedText = btn.textContent || selectedText;
        }
        optionsEl.appendChild(btn);
      });
      triggerEl.textContent = selectedText || fallbackText || '';
    }
    function bindCustomSelectDropdown(selectEl, triggerEl, panelEl, optionsEl, fallbackText) {
      if (!selectEl || !triggerEl || !panelEl || !optionsEl) return;
      if (!triggerEl.dataset.boundDropdown) {
        triggerEl.addEventListener('click', function(e) {
          e.stopPropagation();
          const isOpen = panelEl.classList.contains('is-open');
          closeAllDropdowns();
          if (!isOpen) {
            panelEl.classList.add('is-open');
            triggerEl.classList.add('active');
            triggerEl.setAttribute('aria-expanded', 'true');
          }
        });
        optionsEl.addEventListener('click', function(e) {
          const option = e.target.closest('.sort-option');
          if (!option) return;
          const value = option.getAttribute('data-value') || '';
          selectEl.value = value;
          selectEl.dispatchEvent(new Event('change', { bubbles: true }));
          syncCustomSelectUi(selectEl, triggerEl, optionsEl, fallbackText);
          closeAllDropdowns();
        });
        selectEl.addEventListener('change', function() {
          syncCustomSelectUi(selectEl, triggerEl, optionsEl, fallbackText);
        });
        triggerEl.dataset.boundDropdown = '1';
      }
      syncCustomSelectUi(selectEl, triggerEl, optionsEl, fallbackText);
    }
    function syncSortUi(value) {
      if (!sortOptionsEl || !sortTrigger) return;
      const valueEl = document.getElementById('sortTriggerValue');
      let selectedText = 'Сначала новые по дате';
      sortOptionsEl.querySelectorAll('.sort-option').forEach(function(btn) {
        const on = btn.getAttribute('data-value') === value;
        btn.classList.toggle('active', on);
        if (on) {
          const title = btn.querySelector('.sort-option-title');
          selectedText = (title && title.textContent) ? title.textContent.trim() : btn.textContent.trim();
        }
      });
      if (valueEl) {
        valueEl.textContent = selectedText;
      } else {
        sortTrigger.textContent = selectedText;
      }
    }
    function setDropdownTriggerText(trigger, listEl, filterKey, allLabel) {
      if (!trigger || !listEl) return;
      const sel = getSelectedValues(listEl, filterKey);
      if (sel.size === 0) {
        trigger.innerHTML = '<span class="trigger-placeholder">' + escapeHtml(allLabel) + '</span>';
        return;
      }
      const selected = [];
      listEl.querySelectorAll('input[type=checkbox][data-filter="' + filterKey + '"]').forEach(function(cb) {
        if (!cb.checked) return;
        const label = cb.closest('.checkbox-item');
        const t = label ? label.querySelector('.checkbox__label') : null;
        const text = t ? t.textContent.replace(/\s*\(\d[\d\s]*\)\s*$/, '').trim() : cb.value;
        selected.push({ value: cb.value, text: text });
      });
      const visible = selected.slice(0, 2);
      const tagsHtml = visible.map(function(item) {
        return (
          '<span class="ms-tag">' +
            '<span class="ms-tag-text">' + escapeHtml(item.text) + '</span>' +
            '<span class="ms-tag-remove" role="button" tabindex="0" data-filter-key="' + escapeHtml(filterKey) + '" data-filter-value="' + encodeURIComponent(item.value) + '" aria-label="Убрать фильтр">×</span>' +
          '</span>'
        );
      }).join('');
      const moreHtml = selected.length > 2 ? ('<span class="ms-tag-more">+' + (selected.length - 2) + '</span>') : '';
      trigger.innerHTML = '<span class="trigger-tags">' + tagsHtml + moreHtml + '</span>';
    }

    function checkboxTemplate(id, filterKey, valueEscaped, labelHtml, facetVariants) {
      var varAttr = '';
      if (facetVariants && facetVariants.length > 1) {
        var enc = facetVariants.map(function(v) { return encodeURIComponent(String(v)); }).join('|');
        varAttr = ' data-facet-variants="' + String(enc).replace(/"/g, '&quot;') + '"';
      }
      return (
        '<label class="checkbox" data-selected="false">' +
          '<span class="checkbox__input-wrap"><input type="checkbox" id="' + id + '" data-filter="' + filterKey + '" value="' + valueEscaped + '"' + varAttr + '></span>' +
          '<span class="checkbox__control"><span class="checkbox__indicator"><svg aria-hidden="true" viewBox="0 0 17 18" fill="none"><polyline points="1 9 7 14 15 4"/></svg></span></span>' +
          '<span class="checkbox__content"><span class="checkbox__label">' + labelHtml + '</span></span>' +
        '</label>'
      );
    }
    function expandFacetCheckboxValues(cb) {
      if (!cb) return [];
      var raw = cb.getAttribute('data-facet-variants');
      if (!raw) return [cb.value];
      return raw.split('|').map(function(s) {
        try {
          return decodeURIComponent(s);
        } catch (e) {
          return s;
        }
      });
    }
    function facetDisplayDedupKey(displayLabel, filterKey) {
      var s = String(displayLabel || '').trim();
      if (!s) return '';
      if (filterKey === 'model' && /^[A-Za-z0-9.\-]+$/.test(s)) {
        return s.toUpperCase();
      }
      return s.toLowerCase();
    }

    function syncCheckboxVisualStates(root) {
      const scope = root || document;
      scope.querySelectorAll('.checkbox').forEach(function(el) {
        const input = el.querySelector('input[type=checkbox]');
        if (!input) return;
        el.setAttribute('data-selected', input.checked ? 'true' : 'false');
        el.setAttribute('data-disabled', input.disabled ? 'true' : 'false');
      });
    }

    document.addEventListener('change', function(e) {
      const target = e.target;
      if (!target || target.type !== 'checkbox') return;
      const checkbox = target.closest('.checkbox');
      if (!checkbox) return;
      checkbox.setAttribute('data-selected', target.checked ? 'true' : 'false');
      checkbox.setAttribute('data-disabled', target.disabled ? 'true' : 'false');
    });

    document.addEventListener('click', function(e) {
      const removeBtn = e.target.closest('.ms-tag-remove');
      if (!removeBtn) return;
      e.preventDefault();
      e.stopPropagation();

      const filterKey = removeBtn.getAttribute('data-filter-key');
      const rawValue = removeBtn.getAttribute('data-filter-value') || '';
      const value = decodeURIComponent(rawValue);

      const map = {
        mark: { list: markListEl, trigger: markTrigger, allLabel: 'Все марки' },
        model: { list: modelListEl, trigger: modelTrigger, allLabel: 'Все модели' },
        generation: { list: generationListEl, trigger: generationTrigger, allLabel: 'Все поколения' },
        trim: { list: trimListEl, trigger: trimTrigger, allLabel: 'Все комплектации' }
      };
      const conf = map[filterKey];
      if (!conf || !conf.list) return;

      conf.list.querySelectorAll('input[type=checkbox][data-filter="' + filterKey + '"]').forEach(function(cb) {
        var expanded = expandFacetCheckboxValues(cb);
        if (expanded.indexOf(value) !== -1) cb.checked = false;
      });
      syncCheckboxVisualStates(conf.list);

      if (filterKey === 'mark') {
        setDropdownTriggerText(markTrigger, markListEl, 'mark', 'Все марки');
      } else if (filterKey === 'model') {
        setDropdownTriggerText(modelTrigger, modelListEl, 'model', 'Все модели');
      } else if (filterKey === 'generation') {
        setDropdownTriggerText(generationTrigger, generationListEl, 'generation', 'Все поколения');
      } else if (filterKey === 'trim') {
        setDropdownTriggerText(trimTrigger, trimListEl, 'trim', 'Все комплектации');
      }
      void runApplyFilters();
    });

    document.addEventListener('keydown', function(e) {
      const removeBtn = e.target && e.target.closest ? e.target.closest('.ms-tag-remove') : null;
      if (!removeBtn) return;
      if (e.key !== 'Enter' && e.key !== ' ') return;
      e.preventDefault();
      removeBtn.click();
    });

    // Вспомогательные функции для фильтрации по данным из cars.json / record / inspection
    function getInsuranceCasesCount(car) {
      const r = car.data?.extra?.record_open;
      if (!r) return 0;
      if (Array.isArray(r.accidents) && r.accidents.length) return r.accidents.length;
      const my = Number(r.myAccidentCnt) || 0;
      const other = Number(r.otherAccidentCnt) || 0;
      return my + other;
    }
    function getInsurancePayoutsSum(car) {
      const acc = car.data?.extra?.record_open?.accidents;
      if (!Array.isArray(acc)) return 0;
      return acc.reduce((s, a) => s + (Number(a.insuranceBenefit) || 0), 0);
    }
    function getDamagedCount(car) {
      const bc = car.data?.extra?.inspection_structured?.bodyChanged;
      return bc && typeof bc === 'object' ? Object.keys(bc).length : 0;
    }
    function extractPowerFromString(s) {
      if (!s || typeof s !== 'string') return null;
      const str = String(s).trim();
      const m = str.match(/(\d{2,4})\s*마력/) || str.match(/(\d{2,4})\s*hp/i);
      if (m) return parseInt(m[1], 10);
      return null;
    }
    function getPowerNum(car) {
      const d = (car && (car.data || car)) || {};
      let p = d?.power ?? d?.hp ?? d?.outputHorsepower ?? d?.power_hp;
      if (p !== undefined && p !== null && p !== '') {
        const n = parseInt(String(p).replace(/\D/g, ''), 10);
        if (!Number.isNaN(n) && n >= 20 && n <= 2000) return n;
      }
      p = extractPowerFromString(d?.generation || '') || extractPowerFromString(d?.configuration || '') || extractPowerFromString(d?.gradeName || '');
      return (p != null && p >= 20 && p <= 2000) ? p : null;
    }
    function getEngineVolumeNum(car) {
      const d = car.data?.displacement;
      if (d === undefined || d === null || d === '') return null;
      const s = String(d).replace(/,/, '.').replace(/\s/g, '');
      let n = parseInt(s, 10);
      if (!Number.isNaN(n)) return n;
      const m = s.match(/(\d+\.?\d*)\s*[Ll]?/);
      if (m) n = parseFloat(m[1]);
      return Number.isNaN(n) ? null : (n < 100 ? Math.round(n * 1000) : n);
    }
    function getYearMonthNum(car) {
      const ym = car.data?.yearMonth || car.data?.year || '';
      const str = String(ym).trim();
      if (!str) return null;
      const y = parseInt(str.slice(0, 4), 10);
      const m = parseInt(str.slice(4, 6), 10) || 1;
      if (Number.isNaN(y)) return null;
      return y * 12 + (Number.isNaN(m) ? 0 : m - 1);
    }
    function getInsurancePayoutRub(car) {
      const won = getInsurancePayoutsSum(car);
      if (!won) return 0;
      const d = (car && car.data) || car || {};
      const krw = Number(d.krw_per_usdt) || 1400;
      const rubPerUsdt = Number(d.usdt_rub) || 91;
      if (!krw) return 0;
      return won * (rubPerUsdt / krw);
    }
    function getCarAgeYears(car) {
      const d = (car && car.data) || car || {};
      const y = parseInt(String(d.year || '').replace(/\.0$/, '').slice(0, 4), 10);
      if (Number.isNaN(y)) return null;
      return new Date().getFullYear() - y;
    }
    function paramsForFacet(omitKeys) {
      const p = buildCatalogFilterParams();
      (omitKeys || []).forEach(function(k) { p.delete(k); });
      return p;
    }
    function carMatchesParamsUrl(car, p) {
      const d = (car && car.data) || car || {};
      function csv(key) {
        var v = p.get(key);
        if (!v) return null;
        return v.split(',').map(function(s) { return s.trim(); }).filter(Boolean);
      }
      var marks = csv('marks');
      if (marks && marks.length && marks.indexOf(d.mark) === -1) return false;
      var models = csv('models');
      if (models && models.length && models.indexOf(d.model) === -1) return false;
      var gens = csv('generations');
      var genVal = d.generation || d.configuration || '';
      if (gens && gens.length && gens.indexOf(genVal) === -1) return false;
      var trims = csv('trims');
      var trimVal = d.gradeName || d.configuration || d.generation || '';
      if (trims && trims.length && trims.indexOf(trimVal) === -1) return false;
      var bodies = csv('body');
      if (bodies && bodies.length && bodies.indexOf(d.body_type) === -1) return false;
      var fuels = csv('fuel');
      if (fuels && fuels.length && fuels.indexOf(d.engine_type) === -1) return false;
      var trans = csv('trans');
      if (trans && trans.length && trans.indexOf(d.transmission_type) === -1) return false;
      var colors = csv('color');
      if (colors && colors.length && colors.indexOf(d.color) === -1) return false;
      var pf = p.get('power_from');
      var pt = p.get('power_to');
      var pw = getPowerNum(car);
      if (pf && (pw == null || pw < parseInt(pf, 10))) return false;
      if (pt && (pw == null || pw > parseInt(pt, 10))) return false;
      var ef = p.get('engine_from');
      var et = p.get('engine_to');
      var ev = getEngineVolumeNum(car);
      if (ef && (ev == null || ev < parseInt(ef, 10))) return false;
      if (et && (ev == null || ev > parseInt(et, 10))) return false;
      var prf = p.get('price_from');
      var prt = p.get('price_to');
      var myp = d.my_price != null && d.my_price !== '' ? parseFloat(d.my_price) : null;
      if (prf && (myp == null || myp < parseFloat(prf))) return false;
      if (prt && (myp == null || myp > parseFloat(prt))) return false;
      var mf = p.get('mileage_from');
      var mt = p.get('mileage_to');
      var km = d.km_age != null && d.km_age !== '' ? parseInt(String(d.km_age).replace(/\D/g, ''), 10) : null;
      if (mf && (km == null || km < parseInt(mf, 10))) return false;
      if (mt && (km == null || km > parseInt(mt, 10))) return false;
      var yf = p.get('ym_from');
      var yt = p.get('ym_to');
      var ym = getYearMonthNum(car);
      if (yf && (ym == null || ym < parseInt(yf, 10))) return false;
      if (yt && (ym == null || ym > parseInt(yt, 10))) return false;
      var icf = p.get('ins_cases_from');
      var ict = p.get('ins_cases_to');
      var icn = getInsuranceCasesCount(car);
      if (icf && icn < parseInt(icf, 10)) return false;
      if (ict && icn > parseInt(ict, 10)) return false;
      var ipf = p.get('ins_payout_from');
      var ipt = p.get('ins_payout_to');
      var ipr = getInsurancePayoutRub(car);
      if (ipf && ipr < parseFloat(ipf)) return false;
      if (ipt && ipr > parseFloat(ipt)) return false;
      var df = p.get('damaged_from');
      var dt = p.get('damaged_to');
      var dc = getDamagedCount(car);
      if (df && dc < parseInt(df, 10)) return false;
      if (dt && dc > parseInt(dt, 10)) return false;
      if (p.get('drive_awd') === '1') {
        var drv = d.drive_type || d.prep_drive_type || '';
        if (drv !== 'AWD') return false;
      }
      if (p.get('no_insurance_cases') === '1' && getInsuranceCasesCount(car) !== 0) return false;
      if (p.get('no_insurance_payouts') === '1' && getInsurancePayoutsSum(car) !== 0) return false;
      if (p.get('no_damaged') === '1' && getDamagedCount(car) !== 0) return false;
      if (p.get('passage_cars') === '1') {
        var age = getCarAgeYears(car);
        if (age == null || age < 3 || age > 5) return false;
      }
      return true;
    }
    function sortCarsStatic(list, sortKey) {
      var arr = list.slice();
      function dateVal(c) {
        var d = (c.data) || c;
        var iso = d.offer_created || d.created_at || '';
        var t = Date.parse(String(iso));
        return Number.isNaN(t) ? 0 : t;
      }
      function yearNum(c) {
        var d = (c.data) || c;
        return parseInt(String(d.year || '').slice(0, 4), 10) || 0;
      }
      function priceNum(c) {
        var d = (c.data) || c;
        var v = d.my_price;
        if (v == null || v === '') return null;
        var n = parseFloat(v);
        return Number.isNaN(n) ? null : n;
      }
      function kmNum(c) {
        var d = (c.data) || c;
        var v = d.km_age;
        if (v == null || v === '') return null;
        return parseInt(String(v).replace(/\D/g, ''), 10);
      }
      var sk = sortKey || 'date_new';
      arr.sort(function(a, b) {
        var da = a.data || a;
        var db = b.data || b;
        if (sk === 'date_new') return dateVal(b) - dateVal(a);
        if (sk === 'date_old') return dateVal(a) - dateVal(b);
        if (sk === 'year_new') return yearNum(b) - yearNum(a);
        if (sk === 'year_old') return yearNum(a) - yearNum(b);
        if (sk === 'price_high') {
          var pa = priceNum(a); var pb = priceNum(b);
          if (pa == null && pb == null) return 0;
          if (pa == null) return 1;
          if (pb == null) return -1;
          return pb - pa;
        }
        if (sk === 'price_low') {
          var pa2 = priceNum(a); var pb2 = priceNum(b);
          if (pa2 == null && pb2 == null) return 0;
          if (pa2 == null) return 1;
          if (pb2 == null) return -1;
          return pa2 - pb2;
        }
        if (sk === 'mileage_high') {
          var ka = kmNum(a); var kb = kmNum(b);
          if (ka == null && kb == null) return 0;
          if (ka == null) return 1;
          if (kb == null) return -1;
          return kb - ka;
        }
        if (sk === 'mileage_low') {
          var ka2 = kmNum(a); var kb2 = kmNum(b);
          if (ka2 == null && kb2 == null) return 0;
          if (ka2 == null) return 1;
          if (kb2 == null) return -1;
          return ka2 - kb2;
        }
        return dateVal(b) - dateVal(a);
      });
      return arr;
    }
    const countInfoIcon = document.getElementById('countInfoIcon');

    function positionTooltip(tooltipEl, anchorRect) {
      tooltipEl.style.display = 'block';
      var w = tooltipEl.offsetWidth;
      var h = tooltipEl.offsetHeight;
      var pad = 8;
      var left = anchorRect.left + anchorRect.width / 2 - w / 2;
      var top = anchorRect.top - h - 10;
      left = Math.max(pad, Math.min(left, window.innerWidth - w - pad));
      if (top < pad) top = anchorRect.bottom + 10;
      else top = Math.min(top, window.innerHeight - h - pad);
      tooltipEl.style.left = left + 'px';
      tooltipEl.style.top = top + 'px';
    }

    function showCatalogTaxTooltip(tooltipEl, anchorRect) {
      if (!tooltipEl) return;
      tooltipEl.style.display = 'block';
      tooltipEl.classList.remove('is-visible');
      positionTooltip(tooltipEl, anchorRect);
      void tooltipEl.offsetWidth;
      requestAnimationFrame(function() {
        requestAnimationFrame(function() {
          tooltipEl.classList.add('is-visible');
        });
      });
    }

    function hideCatalogTaxTooltip(tooltipEl) {
      if (!tooltipEl) return;
      tooltipEl.classList.remove('is-visible');
      function finish() {
        tooltipEl.style.display = 'none';
      }
      if (typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        finish();
        return;
      }
      var doneTimer = setTimeout(finish, 300);
      function onEnd(ev) {
        if (ev.target !== tooltipEl) return;
        if (ev.propertyName !== 'opacity' && ev.propertyName !== 'transform') return;
        clearTimeout(doneTimer);
        tooltipEl.removeEventListener('transitionend', onEnd);
        finish();
      }
      tooltipEl.addEventListener('transitionend', onEnd);
    }

    /** Лёгкий spring при pointerdown (как «Сбросить фильтры», но слабее) */
    function bindCardIconPressSpring(el) {
      if (!el || el.dataset.wraPressSpring === '1') return;
      el.dataset.wraPressSpring = '1';
      var current = null;
      el.addEventListener('pointerdown', function() {
        if (typeof el.animate !== 'function') return;
        if (typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        if (current) try { current.cancel(); } catch (e) {}
        current = el.animate(
          [{ transform: 'scale(1)' }, { transform: 'scale(0.97)' }],
          { duration: 55, easing: 'cubic-bezier(0.32, 0, 0.67, 0)' }
        );
        current.onfinish = function() {
          el.animate(
            [{ transform: 'scale(0.97)' }, { transform: 'scale(1)' }],
            { duration: 300, easing: 'cubic-bezier(0.34, 1.22, 0.64, 1)' }
          );
        };
      });
    }

    let currentSort = 'date_new';

    // Форматирование
    function formatYear(raw) {
      if (!raw) return '—';
      raw = String(raw).replace('.0', '');
      const m = raw.match(/(\d{4})(\d{2})/);
      if (!m) return raw;
      return `${m[2]}.${m[1]}`;
    }
    function formatKm(km) {
      if (!km) return '—';
      return Number(km).toLocaleString('ru-RU') + ' км';
    }
    function formatPrice(p) {
      if (p === undefined || p === null) return '';
      return Number(p).toLocaleString('ru-RU') + ' вон';
    }
    // Маппинг корейский → английский (для фильтров и данных)
    const filterMappingKoEn = {
      mark: {
        '현대': 'Hyundai', '기아': 'Kia', '제네시스': 'Genesis', '쌍용': 'SsangYong', '한국GM': 'GM Korea', '르노코리아': 'Renault Korea',
        '벤츠': 'Mercedes-Benz', 'BMW': 'BMW', '아우디': 'Audi', '폭스바겐': 'Volkswagen', '포르쉐': 'Porsche', '미니': 'MINI',
        '볼보': 'Volvo', '렉서스': 'Lexus', '토요타': 'Toyota', '혼다': 'Honda', '닛산': 'Nissan', '인피니티': 'Infiniti',
        '마쓰다': 'Mazda', '미쓰비시': 'Mitsubishi', '스바루': 'Subaru', '스즈키': 'Suzuki', '다이하쓰': 'Daihatsu',
        '포드': 'Ford', '쉐보레': 'Chevrolet', '지프': 'Jeep', '캐딜락': 'Cadillac', '테슬라': 'Tesla',         '폴스타': 'Polestar',
        '랜드로버': 'Land Rover', '재규어': 'Jaguar', '벤틀리': 'Bentley', '롤스로이스': 'Rolls-Royce', '마세라티': 'Maserati',
        '페라리': 'Ferrari', '람보르기니': 'Lamborghini', '알파로메오': 'Alfa Romeo', '피아트': 'Fiat',
        '기타 수입차': 'Other imported', '기타 제조사': 'Other manufacturers', '다이하쯔': 'Daihatsu', '닷지': 'Dodge',
        '도요타': 'Toyota', '동풍소콘': 'DFSK', '로터스': 'Lotus', '르노': 'Renault', '르노코리아(삼성)': 'Renault Korea',
        '링컨': 'Lincoln', '마이바흐': 'Maybach', '마쯔다': 'Mazda', '맥라렌': 'McLaren', '미쯔비시': 'Mitsubishi',
        '미쯔오까': 'Mitsuoka', '북기은상': 'BAIC Yinxiang', '사브': 'Saab', '신위안': 'Shineray', '머큐리': 'Mercury',
        '알파 로메오': 'Alfa Romeo', '애스턴마틴': 'Aston Martin', '어큐라': 'Acura', '이네오스': 'INEOS',
        '지리': 'Geely', '크라이슬러': 'Chrysler', '푸조': 'Peugeot', '험머': 'Hummer', '기타': 'Other',
        '/DS': 'DS Automobiles', '(GM )': 'General Motors', '(GM)': 'General Motors', 'GM ': 'General Motors'
      },
      bodyType: {
        '세단': 'Sedan', 'SUV': 'SUV', '해치백': 'Hatchback', '왜건': 'Wagon', '쿠페': 'Coupe', '픽업': 'Pickup', '밴': 'Van',
        '중형차': 'Midsize', '대형차': 'Full-size', '소형차': 'Compact', '경차': 'Light car', '미니밴': 'Minivan', 'RV': 'RV',
        '스포츠카': 'Sports car', '승합차': 'Minibus', '화물차': 'Commercial vehicle',
        '크로스오버': 'Crossover', '리무진': 'Limousine', '컨버터블': 'Convertible',
        '경승합차': 'Minibus', '준중형차': 'Compact', '기타': 'Other'
      },
      engineType: {
        '가솔린': 'Gasoline', '디젤': 'Diesel', 'LPG': 'LPG', 'LPG/가솔린': 'LPG/Gasoline', '하이브리드': 'Hybrid',
        '가솔린+전기': 'Hybrid', '전기': 'Electric', '수소': 'Hydrogen', '디젤+전기': 'Diesel Hybrid',
        '바이퓨얼': 'Dual fuel', '친환경': 'Eco', '수소+전기': 'Hydrogen EV', '가솔린+전기+LPG': 'Hybrid LPG',
        '+CNG': 'CNG', 'CNG+': 'CNG', 'CNG': 'CNG',
        '+LPG': 'LPG', 'LPG+': 'LPG', '기타': 'Other'
      },
      transmission: {
        '자동': 'Automatic', '수동': 'Manual', '오토': 'Automatic', '세미자동': 'Semi-Auto', 'CVT': 'CVT', '듀얼 클러치': 'DCT',
        'ISG': 'ISG', '감속기': 'Reducer', '비전동': 'Non-powered',
        '세미오토': 'Semi-Auto', '기타': 'Other', '001': 'Other'
      },
      color: {
        '검정': 'Black', '검정색': 'Black', '흰색': 'White', '은색': 'Silver', '회색': 'Gray', '빨간색': 'Red',
        '파란색': 'Blue', '남색': 'Navy', '베이지': 'Beige', '갈색': 'Brown', '녹색': 'Green', '노란색': 'Yellow', '주황': 'Orange',
        '골드': 'Gold', '실버': 'Silver', '블랙': 'Black', '화이트': 'White', '레드': 'Red', '블루': 'Blue', '그레이': 'Gray', '그린': 'Green',
        '보라색': 'Purple', '연금색': 'Light gold', '연두색': 'Lime green', '은하색': 'Silver gray', '자주색': 'Purple', '쥐색': 'Dark gray', '진주색': 'Pearl', '청색': 'Blue', '하늘색': 'Sky blue',
        '검정투톤': 'Black two-tone', '금색투톤': 'Gold two-tone', '은색투톤': 'Silver two-tone',
        '진주투톤': 'Pearl two-tone', '흰색투톤': 'White two-tone', '갈색투톤': 'Brown two-tone',
        '갈대색': 'Khaki', '담녹색': 'Light green', '명은색': 'Silver gray', '분홍색': 'Pink', '주황색': 'Orange', '청록색': 'Turquoise'
      },
      // Привод (drive_type / prep_drive_type); в encar_mapping «type» — другой смысл, эти ключи перекрывают при совпадении.
      type: {
        'AWD': 'AWD', '4WD': 'AWD', '4x4': 'AWD', '2WD': '2WD', 'FWD': 'FWD', 'RWD': 'RWD',
        '사륜구동': 'AWD', '사륜': 'AWD', '전륜구동': 'FWD', '전륜': 'FWD', '후륜구동': 'RWD', '후륜': 'RWD'
      }
    };
    function toDisplayEn(val, category) {
      if (!val) return val;
      const s = String(val).trim();
      const map = category && filterMappingKoEn[category] ? filterMappingKoEn[category] : null;
      if (!map) return val;
      if (map[s]) return map[s];
      const exactKey = Object.keys(map).find(k => String(k).trim() === s);
      if (exactKey) return map[exactKey];
      const sLower = s.toLowerCase();
      const keyLower = Object.keys(map).find(k => String(k).trim().toLowerCase() === sLower);
      if (keyLower) return map[keyLower];
      return val;
    }
    // Словарь корейских слов/фраз в поколениях и комплектациях (когда маппинг не дал EN или вернул то же)
    const koreanPhraseToEn = {
      '플러그인 하이브리드': 'Plug-in Hybrid', '플러그인 HEV': 'Plug-in HEV', '하이브리드': 'Hybrid',
      '투어링': 'Touring', '투어러': 'Tourer', '투어': 'Tour',
      '프리미엄 초이스': 'Premium Choice', '프리미엄 플러스': 'Premium Plus', '프리미엄 패밀리': 'Premium Family', '프리미엄 밀레니얼': 'Premium Millennial', '프리미엄': 'Premium',
      '익스클루시브 스페셜': 'Exclusive Special', '익스클루시브': 'Exclusive',
      '인스퍼레이션': 'Inspiration', '캘리그래피': 'Calligraphy', '르블랑': 'Le Blanc', '아너스': 'Honors',
      '스마트': 'Smart', '모던': 'Modern', '럭셔리': 'Luxury', '스포츠': 'Sport', '로열': 'Royal', '프리미어': 'Premiere',
      '컬렉션': 'Collection', '초이스': 'Choice', '스페셜': 'Special', '플러스': 'Plus', '패밀리': 'Family', '밀레니얼': 'Millennial',
      'N 라인': 'N Line', 'N Line': 'N Line',
      '수출형': 'Export', '기본형': 'Base', '이지팩': 'Easy Pack', '어드밴스팩': 'Advance Pack',
      '리미티드': 'Limited', '시그니처': 'Signature', '플래티넘': 'Platinum', '엘리트': 'Elite', '컴포트': 'Comfort', '베이직': 'Basic',
      '세부등급 없음': '', ' (세부등급 없음)': '', '(세부등급 없음)': ''
    };
    const koreanPhraseKeys = Object.keys(koreanPhraseToEn).sort((a, b) => b.length - a.length);
    function applyKoreanPhraseFallback(str) {
      if (!str || typeof str !== 'string') return str;
      let out = str.trim();
      for (let i = 0; i < koreanPhraseKeys.length; i++) {
        const ko = koreanPhraseKeys[i];
        const en = koreanPhraseToEn[ko];
        if (out.indexOf(ko) !== -1) out = out.split(ko).join(en || ko);
      }
      return out.replace(/\s+/g, ' ').trim();
    }
    function containsHangul(str) {
      return /[\u1100-\u11FF\u3130-\u318F\uAC00-\uD7AF]/.test(String(str || ''));
    }
    function stripKoreanForTitlePart(str) {
      if (!str) return '';
      return String(str)
        .replace(/[\u1100-\u11FF\u3130-\u318F\uAC00-\uD7AF]+/g, ' ')
        .replace(/\(\s*\)/g, ' ')
        .replace(/\[\s*\]/g, ' ')
        .replace(/\s{2,}/g, ' ')
        .trim();
    }
    function sanitizeUiLabel(label) {
      if (!label) return '';
      if (!containsHangul(label)) return label;
      return stripKoreanForTitlePart(label) || '';
    }
    // Перевод для UI на русский: тип кузова, топливо, коробка, цвет (без корейских символов в выводе)
    const displayRu = {
      'AWD': 'Полный', '2WD': '2WD', 'FWD': 'Передний', 'RWD': 'Задний',
      '가솔린': 'Бензин', '디젤': 'Дизель', 'LPG': 'Газ', 'LPG/가솔린': 'Газ/бензин', '하이브리드': 'Гибрид', '전기': 'Электро', '가솔린+전기': 'Гибрид', '수소': 'Водород', '디젤+전기': 'Дизель + Гибрид',
      'Gasoline': 'Бензин', 'Diesel': 'Дизель', 'Electric': 'Электро', 'Hybrid': 'Гибрид', 'Hydrogen': 'Водород', 'LPG/Gasoline': 'Газ/бензин', 'Diesel Hybrid': 'Дизель + Гибрид',
      'CNG': 'CNG', 'Other': 'Прочее',
      '세단': 'Седан', 'SUV': 'Внедорожник', '해치백': 'Хэтчбек', '왜건': 'Универсал', '쿠페': 'Купе', '픽업': 'Пикап', '밴': 'Фургон', '중형차': 'Седан среднего класса', '대형차': 'Седан полноразмерный', '소형차': 'Компакт', '경차': 'Микролитражный', '미니밴': 'Минивэн', 'RV': 'Внедорожник', '스포츠카': 'Спорткар', '승합차': 'Микроавтобус', '화물차': 'Грузовой автомобиль',
      'Sedan': 'Седан', 'Hatchback': 'Хэтчбек', 'Wagon': 'Универсал', 'Coupe': 'Купе', 'Pickup': 'Пикап', 'Van': 'Фургон', 'Midsize': 'Седан среднего класса', 'Full-size': 'Седан полноразмерный', 'Compact': 'Компакт', 'Minivan': 'Минивэн', 'Light car': 'Микролитражный', 'Sports car': 'Спорткар', 'Minibus': 'Микроавтобус', 'Commercial vehicle': 'Грузовой автомобиль',
      'Crossover': 'Кроссовер', 'Convertible': 'Кабриолет', 'Limousine': 'Лимузин', 'Dual fuel': 'Двухтопливный', 'Eco': 'Экологичный', 'Hydrogen EV': 'Водород + электро', 'Hybrid LPG': 'Гибрид LPG', 'ISG': 'ISG', 'Reducer': 'Редуктор', 'Non-powered': 'Без привода',
      '자동': 'Автоматическая', '수동': 'Механическая', '오토': 'Автоматическая', '세미자동': 'Роботизированная', 'CVT': 'Вариатор', '듀얼 클러치': 'Роботизированная',
      'Automatic': 'Автоматическая', 'Manual': 'Механическая', 'Semi-Auto': 'Роботизированная', 'DCT': 'Роботизированная',
      'Black two-tone': 'Черный двухцветный', 'Gold two-tone': 'Золотой двухцветный', 'Silver two-tone': 'Серебристый двухцветный',
      'Pearl two-tone': 'Перламутровый двухцветный', 'White two-tone': 'Белый двухцветный', 'Brown two-tone': 'Коричневый двухцветный',
      'Khaki': 'Хаки', 'Light green': 'Светло-зеленый', 'Pink': 'Розовый', 'Turquoise': 'Бирюзовый',
      '검정': 'Чёрный', '흰색': 'Белый', '검정색': 'Чёрный', '은색': 'Серебристый', '회색': 'Серый', '빨간색': 'Красный', '파란색': 'Синий', '남색': 'Тёмно-синий', '베이지': 'Бежевый', '갈색': 'Коричневый', '녹색': 'Зелёный', '노란색': 'Жёлтый', '주황': 'Оранжевый', '골드': 'Золотой', '실버': 'Серебро', '블랙': 'Чёрный', '화이트': 'Белый', '레드': 'Красный', '블루': 'Синий', '그레이': 'Серый', '그린': 'Зелёный',
      'Black': 'Чёрный', 'White': 'Белый', 'Silver': 'Серебристый', 'Gray': 'Серый', 'Grey': 'Серый', 'Red': 'Красный', 'Blue': 'Синий', 'Navy': 'Тёмно-синий', 'Beige': 'Бежевый', 'Brown': 'Коричневый', 'Green': 'Зелёный', 'Yellow': 'Жёлтый', 'Orange': 'Оранжевый', 'Gold': 'Золотой', 'Purple': 'Фиолетовый', 'Lime green': 'Салатовый', 'Light gold': 'Светло-золотистый', 'Silver gray': 'Серебристо-серый', 'Dark gray': 'Тёмно-серый', 'Pearl': 'Перламутровый', 'Sky blue': 'Голубой',
      '은회색': 'Серебристо-серый', '챠콜': 'Графитовый', '다크그레이': 'Тёмно-серый', '다크블루': 'Тёмно-синий', '다크레드': 'Тёмно-красный', '라이트그레이': 'Светло-серый', '라이트블루': 'Светло-синий', '민트': 'Мятный', '버건디': 'Бордовый', '아이보리': 'Слоновая кость', '카키': 'Хаки', '타이탄': 'Титан', '펄화이트': 'Жемчужно-белый', '크림': 'Кремовый',
      '보라색': 'Фиолетовый', '연금색': 'Светло-золотистый', '연두색': 'Салатовый', '은하색': 'Серебристо-серый', '자주색': 'Пурпурный', '쥐색': 'Тёмно-серый', '진주색': 'Перламутровый', '청색': 'Синий', '하늘색': 'Голубой'
    };
    function toDisplayRu(val) {
      if (!val) return val;
      const s = String(val).trim();
      return displayRu[s] || displayRu[s.replace(/\s+/g, ' ')] || (function() {
        const lower = s.toLowerCase();
        for (const k of Object.keys(displayRu)) {
          if (k.toLowerCase() === lower) return displayRu[k];
        }
        return val;
      })();
    }
    function filterOptionLabel(val, category) {
      const s = String(val || '').trim();
      const raw = s;
      const ruCategories = ['bodyType', 'engineType', 'transmission', 'color'];
      const isRuCategory = ruCategories.indexOf(category) >= 0;
      let out = '';
      if (isRuCategory) {
        const en = toDisplayEn(s, category);
        out = sanitizeUiLabel(toDisplayRu(en || s) || en || s);
      } else {
        let en = toDisplayEn(s, category);
        if (en !== s) {
          out = sanitizeUiLabel(en);
        } else if (['mark', 'model', 'generation', 'type', 'trim'].indexOf(category) >= 0) {
          // Марка/модель и т.д. — не гонять через toDisplayRu (там словарь цветов и кузовов: «Pearl», «Gray» и т.п. ломали подписи).
          const fallback = applyKoreanPhraseFallback(s);
          out = sanitizeUiLabel(fallback || s);
        } else {
          out = sanitizeUiLabel(toDisplayRu(s) || s);
        }
      }
      if (category === 'mark') {
        out = String(out || raw || '')
          .replace(/^\(([^)]+)\)$/, '$1')
          .replace(/^\//, '')
          .replace(/\s+/g, ' ')
          .trim();
      }
      if (!out && raw) out = isRuCategory ? 'Прочее' : raw;
      if (!out && val != null && String(val).length) out = String(val).trim();
      return out || 'Прочее';
    }
    function buildCatalogFilterParams() {
      syncCatalogMarketFromLocation();
      const p = new URLSearchParams();
      function addCsv(key, iterable) {
        const a = [...iterable].filter(Boolean);
        if (a.length) p.set(key, a.join(','));
      }
      addCsv('marks', getSelectedValues(markListEl, 'mark'));
      addCsv('models', getSelectedValues(modelListEl, 'model'));
      addCsv('generations', getSelectedValues(generationListEl, 'generation'));
      addCsv('trims', getSelectedValues(trimListEl, 'trim'));

      const bodies = [];
      document.querySelectorAll('#bodyList input[type=checkbox]:checked').forEach(function(cb) { bodies.push(cb.value); });
      addCsv('body', bodies);
      const fuels = [];
      document.querySelectorAll('#fuelList input[type=checkbox]:checked').forEach(function(cb) { fuels.push(cb.value); });
      addCsv('fuel', fuels);
      const trans = [];
      document.querySelectorAll('#transmissionList input[type=checkbox]:checked').forEach(function(cb) { trans.push(cb.value); });
      addCsv('trans', trans);
      const colors = [];
      document.querySelectorAll('input[data-filter="color"]:checked').forEach(function(cb) { colors.push(cb.value); });
      addCsv('color', colors);

      function el(id) { return document.getElementById(id); }
      var pf = el('powerFrom');
      if (pf && pf.value) p.set('power_from', pf.value);
      var pt = el('powerTo');
      if (pt && pt.value) p.set('power_to', pt.value);
      var ef = el('engineFrom');
      if (ef && ef.value) p.set('engine_from', ef.value);
      var et = el('engineTo');
      if (et && et.value) p.set('engine_to', et.value);
      var prf = el('priceFrom');
      if (prf && prf.value !== '') p.set('price_from', String(prf.value));
      var prt = el('priceTo');
      if (prt && prt.value !== '') p.set('price_to', String(prt.value));
      var mf = el('mileageFrom');
      if (mf && mf.value) p.set('mileage_from', mf.value);
      var mt = el('mileageTo');
      if (mt && mt.value) p.set('mileage_to', mt.value);

      var yearFrom = el('yearFrom') && el('yearFrom').value ? parseInt(el('yearFrom').value, 10) : null;
      var monthFrom = el('monthFrom') && el('monthFrom').value ? el('monthFrom').value : null;
      var yearTo = el('yearTo') && el('yearTo').value ? parseInt(el('yearTo').value, 10) : null;
      var monthTo = el('monthTo') && el('monthTo').value ? el('monthTo').value : null;
      var fromYm = (yearFrom && yearFrom > 0) ? yearFrom * 12 + (monthFrom ? parseInt(monthFrom, 10) - 1 : 0) : null;
      var toYm = (yearTo && yearTo > 0) ? yearTo * 12 + (monthTo ? parseInt(monthTo, 10) - 1 : 11) : null;
      if (fromYm !== null) p.set('ym_from', String(fromYm));
      if (toYm !== null) p.set('ym_to', String(toYm));

      var icf = el('insuranceCasesFrom');
      if (icf && icf.value) p.set('ins_cases_from', icf.value);
      var ict = el('insuranceCasesTo');
      if (ict && ict.value) p.set('ins_cases_to', ict.value);
      var ipf = el('insurancePayoutsFrom');
      if (ipf && ipf.value) p.set('ins_payout_from', ipf.value);
      var ipt = el('insurancePayoutsTo');
      if (ipt && ipt.value) p.set('ins_payout_to', ipt.value);
      var df = el('damagedFrom');
      if (df && df.value) p.set('damaged_from', df.value);
      var dt = el('damagedTo');
      if (dt && dt.value) p.set('damaged_to', dt.value);

      var driveChk = el('filterDriveAwd');
      if (driveChk && driveChk.checked) p.set('drive_awd', '1');
      var nic = el('filterNoInsuranceCases');
      if (nic && nic.checked) p.set('no_insurance_cases', '1');
      var nip = el('filterNoInsurancePayouts');
      if (nip && nip.checked) p.set('no_insurance_payouts', '1');
      var nd = el('filterNoDamaged');
      if (nd && nd.checked) p.set('no_damaged', '1');
      var pvc = el('filterPassageCars');
      if (pvc && pvc.checked) p.set('passage_cars', '1');

      if (CATALOG_SOURCE) p.set('source', CATALOG_SOURCE);
      if (CATALOG_REGION) p.set('region', CATALOG_REGION);

      return p;
    }

    /** «Пустые фильтры» для прогрева фасетов: режим Кореи (`source=encar`) не считается фильтром. */
    function buildCatalogFilterParamsSansDefaultSource() {
      var p = buildCatalogFilterParams();
      if (CATALOG_REGION === 'korea' && p.get('source') === 'encar') {
        p.delete('source');
      }
      if (CATALOG_REGION === 'korea' && p.get('region') === 'korea') {
        p.delete('region');
      }
      if (CATALOG_REGION === 'china' && (p.get('source') === 'dongchedi' || p.get('source') === 'china')) {
        p.delete('source');
      }
      if (CATALOG_REGION === 'china' && p.get('region') === 'china') {
        p.delete('region');
      }
      return p;
    }

    /** Плитка «Из Китая»: при медленном /api/stats подставляем meta.total из первого безфильтрового запроса /api/cars. */
    function maybeSyncMarketChinaCountFromCarsMeta(metaTotal) {
      if (CATALOG_REGION !== 'china') return;
      var el = document.getElementById('marketChinaCount');
      if (!el) return;
      try {
        if (buildCatalogFilterParamsSansDefaultSource().toString() !== '') return;
      } catch (e) {
        return;
      }
      if (typeof metaTotal !== 'number' || !Number.isFinite(metaTotal) || metaTotal < 0) return;
      el.textContent = metaTotal.toLocaleString('ru-RU');
    }

    function updateFilterCountBadge() {
      const selectedMarks = getSelectedValues(markListEl, 'mark');
      const selectedModels = getSelectedValues(modelListEl, 'model');
      const selectedGenerations = getSelectedValues(generationListEl, 'generation');
      const selectedTrims = getSelectedValues(trimListEl, 'trim');
      const selectedBody = new Set();
      const selectedFuel = new Set();
      const selectedTrans = new Set();
      const selectedColor = new Set();
      document.querySelectorAll('#bodyList input[type=checkbox]:checked').forEach(function(cb) { selectedBody.add(cb.value); });
      document.querySelectorAll('#fuelList input[type=checkbox]:checked').forEach(function(cb) { selectedFuel.add(cb.value); });
      document.querySelectorAll('#transmissionList input[type=checkbox]:checked').forEach(function(cb) { selectedTrans.add(cb.value); });
      document.querySelectorAll('input[data-filter="color"]:checked').forEach(function(cb) { selectedColor.add(cb.value); });

      function numEl(id, parseFn) {
        var node = document.getElementById(id);
        if (!node || node.value === '' || node.value == null) return null;
        var v = parseFn(node.value, 10);
        return Number.isNaN(v) ? null : v;
      }
      function floatEl(id) {
        var node = document.getElementById(id);
        if (!node || node.value === '' || node.value == null) return null;
        var v = parseFloat(node.value);
        return Number.isNaN(v) ? null : v;
      }
      const powerFrom = numEl('powerFrom', parseInt);
      const powerTo = numEl('powerTo', parseInt);
      const engineFrom = numEl('engineFrom', parseInt);
      const engineTo = numEl('engineTo', parseInt);
      const priceFrom = floatEl('priceFrom');
      const priceTo = floatEl('priceTo');
      const mileageFrom = numEl('mileageFrom', parseInt);
      const mileageTo = numEl('mileageTo', parseInt);
      var yf = document.getElementById('yearFrom');
      var mf = document.getElementById('monthFrom');
      var yt = document.getElementById('yearTo');
      var mt = document.getElementById('monthTo');
      const yearFrom = yf && yf.value ? parseInt(yf.value, 10) : null;
      const monthFrom = mf && mf.value ? mf.value : null;
      const yearTo = yt && yt.value ? parseInt(yt.value, 10) : null;
      const monthTo = mt && mt.value ? mt.value : null;
      var driveEl = document.getElementById('filterDriveAwd');
      const driveAwdOnly = !!(driveEl && driveEl.checked);
      const insuranceCasesFrom = numEl('insuranceCasesFrom', parseInt);
      const insuranceCasesTo = numEl('insuranceCasesTo', parseInt);
      var nic = document.getElementById('filterNoInsuranceCases');
      const noInsuranceCases = !!(nic && nic.checked);
      const insurancePayoutsFrom = floatEl('insurancePayoutsFrom');
      const insurancePayoutsTo = floatEl('insurancePayoutsTo');
      var nip = document.getElementById('filterNoInsurancePayouts');
      const noInsurancePayouts = !!(nip && nip.checked);
      const damagedFrom = numEl('damagedFrom', parseInt);
      const damagedTo = numEl('damagedTo', parseInt);
      var nd = document.getElementById('filterNoDamaged');
      const noDamaged = !!(nd && nd.checked);
      var pac = document.getElementById('filterPassageCars');
      const passageCars = !!(pac && pac.checked);

      let activeCount = 0;
      if (selectedMarks.size > 0) activeCount++;
      if (selectedModels.size > 0) activeCount++;
      if (selectedGenerations.size > 0) activeCount++;
      if (selectedTrims.size > 0) activeCount++;
      activeCount += selectedBody.size + selectedFuel.size + selectedTrans.size + selectedColor.size;
      if (powerFrom !== null) activeCount++;
      if (powerTo !== null) activeCount++;
      if (engineFrom !== null) activeCount++;
      if (engineTo !== null) activeCount++;
      if (priceFrom !== null) activeCount++;
      if (priceTo !== null) activeCount++;
      if (mileageFrom !== null) activeCount++;
      if (mileageTo !== null) activeCount++;
      if (yearFrom !== null) activeCount++;
      if (monthFrom) activeCount++;
      if (yearTo !== null) activeCount++;
      if (monthTo) activeCount++;
      if (driveAwdOnly) activeCount++;
      if (insuranceCasesFrom !== null) activeCount++;
      if (insuranceCasesTo !== null) activeCount++;
      if (noInsuranceCases) activeCount++;
      if (insurancePayoutsFrom !== null) activeCount++;
      if (insurancePayoutsTo !== null) activeCount++;
      if (noInsurancePayouts) activeCount++;
      if (damagedFrom !== null) activeCount++;
      if (damagedTo !== null) activeCount++;
      if (noDamaged) activeCount++;
      if (passageCars) activeCount++;
      if (filterCountEl) filterCountEl.innerText = activeCount;
      if (filtersBadge) filtersBadge.textContent = String(activeCount);
    }

    function renderFacetCheckboxList(container, rows, filterKey, labelCategory) {
      if (!container || !Array.isArray(rows)) return;
      const preserve = new Set();
      container.querySelectorAll('input[type=checkbox][data-filter="' + filterKey + '"]:checked').forEach(function(cb) {
        expandFacetCheckboxValues(cb).forEach(function(v) { preserve.add(v); });
      });
      const countMap = {};
      rows.forEach(function(r) {
        if (!r || r.value == null || r.value === '') return;
        var v = String(r.value).trim().replace(/\u00A0/g, ' ');
        if (!v) return;
        countMap[v] = (countMap[v] || 0) + Number(r.count || 0);
      });
      let vals = Object.keys(countMap);
      const dedupFilterKeys = ['mark', 'model', 'generation', 'trim', 'body', 'fuel', 'transmission', 'color'];
      if (dedupFilterKeys.indexOf(filterKey) >= 0) {
        const byGroup = {};
        vals.forEach(function(v) {
          const display = String(labelCategory ? filterOptionLabel(v, labelCategory) : v).trim();
          if (!display) return;
          const dedupK = facetDisplayDedupKey(display, filterKey);
          if (!dedupK) return;
          if (!byGroup[dedupK]) byGroup[dedupK] = { values: [], count: 0 };
          byGroup[dedupK].values.push(v);
          byGroup[dedupK].count += Number(countMap[v] || 0);
        });
        const merged = Object.keys(byGroup).map(function(dk) {
          const g = byGroup[dk];
          const sorted = g.values.slice().sort();
          let rep = sorted[0];
          for (var i = 0; i < sorted.length; i++) {
            if (preserve.has(sorted[i])) {
              rep = sorted[i];
              break;
            }
          }
          return { value: rep, variants: sorted, count: g.count };
        });
        merged.sort(function(a, b) {
          const la = labelCategory ? filterOptionLabel(a.value, labelCategory) : String(a.value);
          const lb = labelCategory ? filterOptionLabel(b.value, labelCategory) : String(b.value);
          return String(la).localeCompare(String(lb), 'ru');
        });
        renderCheckboxesWithCounts(container, merged, labelCategory, filterKey);
        container.querySelectorAll('input[type=checkbox][data-filter="' + filterKey + '"]').forEach(function(cb) {
          var exp = expandFacetCheckboxValues(cb);
          cb.checked = exp.some(function(v) { return preserve.has(v); });
        });
        syncCheckboxVisualStates(container);
        return;
      }
      vals.sort(function(a, b) {
        const la = labelCategory ? filterOptionLabel(a, labelCategory) : String(a);
        const lb = labelCategory ? filterOptionLabel(b, labelCategory) : String(b);
        return String(la).localeCompare(String(lb), 'ru');
      });
      const asMerged = vals.map(function(v) {
        return { value: v, variants: [v], count: countMap[v] || 0 };
      });
      renderCheckboxesWithCounts(container, asMerged, labelCategory, filterKey);
      container.querySelectorAll('input[type=checkbox][data-filter="' + filterKey + '"]').forEach(function(cb) {
        var exp = expandFacetCheckboxValues(cb);
        cb.checked = exp.some(function(v) { return preserve.has(v); });
      });
      syncCheckboxVisualStates(container);
    }

    function renderColorFilterFromFacets(colorRows) {
      const colorListVisible = document.getElementById('colorListVisible');
      const colorModalList = document.getElementById('colorModalList');
      const showMoreColorsBtn = document.getElementById('showMoreColorsBtn');
      if (!colorListVisible || !colorModalList) return;

      const preserve = new Set();
      document.querySelectorAll('input[data-filter="color"]:checked').forEach(function(cb) { preserve.add(cb.value); });

      const countMap = {};
      (colorRows || []).forEach(function(r) {
        if (r && r.value != null && r.value !== '') countMap[r.value] = (countMap[r.value] || 0) + Number(r.count || 0);
      });
      const allColorsRaw = Object.keys(countMap);
      const colorByLabel = {};
      allColorsRaw.forEach(function(v) {
        const k = String(filterOptionLabel(v, 'color') || v).trim().toLowerCase();
        if (!k) return;
        if (!colorByLabel[k]) colorByLabel[k] = { value: v, count: 0 };
        colorByLabel[k].count += Number(countMap[v] || 0);
        if (preserve.has(v)) colorByLabel[k].value = v;
      });
      const allColors = Object.keys(colorByLabel).map(function(k) { return colorByLabel[k].value; }).sort(function(a, b) {
        return (filterOptionLabel(a, 'color') || '').localeCompare(filterOptionLabel(b, 'color') || '', 'ru');
      });

      colorListVisible.innerHTML = '';
      colorModalList.innerHTML = '';
      const restColors = allColors.slice(4);

      function appendColor(container, val, idPrefix, idx) {
        const div = document.createElement('div');
        div.className = 'checkbox-item';
        const safe = String(val).replace(/[^\w\-]/g, '_').slice(0, 80);
        const id = idPrefix + idx + '_' + safe;
        const labelText = filterOptionLabel(val, 'color');
        const group = colorByLabel[String(labelText).trim().toLowerCase()];
        const cnt = group ? group.count : (countMap[val] || 0);
        const suffix = cnt != null ? (' <span class="opt-count">(' + Number(cnt).toLocaleString('ru-RU') + ')</span>') : '';
        div.innerHTML = checkboxTemplate(id, 'color', escapeHtml(val), escapeHtml(labelText) + suffix, null);
        container.appendChild(div);
      }
      allColors.slice(0, 4).forEach(function(val, idx) { appendColor(colorListVisible, val, 'filter-color-', idx); });
      allColors.forEach(function(val, idx) { appendColor(colorModalList, val, 'filter-color-modal-', idx); });

      document.querySelectorAll('input[data-filter="color"]').forEach(function(cb) {
        cb.checked = preserve.has(cb.value);
      });
      syncCheckboxVisualStates(colorListVisible);
      syncCheckboxVisualStates(colorModalList);
      syncCheckboxVisualStates(document);
      if (showMoreColorsBtn) showMoreColorsBtn.style.display = restColors.length > 0 ? 'block' : 'none';
    }

    function applyFacetsApiPayload(data, reqId) {
      if (reqId != null && reqId !== catalogRequestId) return;
      if (!data || typeof data !== 'object') return;
      function cascade(container, rows, filterKey, labelCat, trigger, allLabel) {
        if (!container) return;
        renderFacetCheckboxList(container, rows || [], filterKey, labelCat);
        if (trigger) setDropdownTriggerText(trigger, container, filterKey, allLabel);
      }

      cascade(markListEl, data.marks, 'mark', 'mark', markTrigger, 'Все марки');

      cascade(modelListEl, data.models, 'model', 'model', modelTrigger, 'Все модели');
      cascade(generationListEl, data.generations, 'generation', 'generation', generationTrigger, 'Все поколения');
      cascade(trimListEl, data.trims, 'trim', 'trim', trimTrigger, 'Все комплектации');

      renderFacetCheckboxList(document.getElementById('bodyList'), data.bodies || [], 'body', 'bodyType');
      renderFacetCheckboxList(document.getElementById('fuelList'), data.fuels || [], 'fuel', 'engineType');
      renderFacetCheckboxList(document.getElementById('transmissionList'), data.transmissions || [], 'transmission', 'transmission');
      renderColorFilterFromFacets(data.colors || []);

      syncCascadeSlotVisibility();
      scheduleRepositionOpenCascadePanels();
    }

    function refreshFacetsFromStaticCache(expectedParamSnap) {
      if (expectedParamSnap != null && expectedParamSnap !== buildCatalogFilterParams().toString()) return;
      if (!staticCatalogCache || !staticCatalogCache.length) return;
      var pMarks = paramsForFacet(['marks']);
      var pModels = paramsForFacet(['models']);
      var pGens = paramsForFacet(['generations']);
      var pTrims = paramsForFacet(['trims']);
      var pBody = paramsForFacet(['body']);
      var pFuel = paramsForFacet(['fuel']);
      var pTrans = paramsForFacet(['trans']);
      var pColor = paramsForFacet(['color']);
      var maps = {
        marks: Object.create(null),
        models: Object.create(null),
        generations: Object.create(null),
        trims: Object.create(null),
        body: Object.create(null),
        fuel: Object.create(null),
        trans: Object.create(null),
        color: Object.create(null),
      };
      for (var i = 0, n = staticCatalogCache.length; i < n; i++) {
        var car = staticCatalogCache[i];
        var d = car.data || car;
        if (carMatchesParamsUrl(car, pMarks)) {
          var mk = d.mark;
          if (mk != null && mk !== '') maps.marks[mk] = (maps.marks[mk] || 0) + 1;
        }
        if (carMatchesParamsUrl(car, pModels)) {
          var mo = d.model;
          if (mo != null && mo !== '') maps.models[mo] = (maps.models[mo] || 0) + 1;
        }
        if (carMatchesParamsUrl(car, pGens)) {
          var g = d.generation || d.configuration || '';
          if (g !== '') maps.generations[g] = (maps.generations[g] || 0) + 1;
        }
        if (carMatchesParamsUrl(car, pTrims)) {
          var tr = d.gradeName || d.configuration || d.generation || '';
          if (tr !== '') maps.trims[tr] = (maps.trims[tr] || 0) + 1;
        }
        if (carMatchesParamsUrl(car, pBody)) {
          var b = d.body_type;
          if (b != null && b !== '') maps.body[b] = (maps.body[b] || 0) + 1;
        }
        if (carMatchesParamsUrl(car, pFuel)) {
          var f = d.engine_type;
          if (f != null && f !== '') maps.fuel[f] = (maps.fuel[f] || 0) + 1;
        }
        if (carMatchesParamsUrl(car, pTrans)) {
          var tx = d.transmission_type;
          if (tx != null && tx !== '') maps.trans[tx] = (maps.trans[tx] || 0) + 1;
        }
        if (carMatchesParamsUrl(car, pColor)) {
          var col = d.color;
          if (col != null && col !== '') maps.color[col] = (maps.color[col] || 0) + 1;
        }
      }
      function facetMapToRows(m) {
        return Object.keys(m).map(function(value) { return { value: value, count: m[value] }; });
      }
      function cascade(container, rows, filterKey, labelCat, trigger, allLabel) {
        if (!container) return;
        renderFacetCheckboxList(container, rows || [], filterKey, labelCat);
        if (trigger) setDropdownTriggerText(trigger, container, filterKey, allLabel);
      }
      cascade(markListEl, facetMapToRows(maps.marks), 'mark', 'mark', markTrigger, 'Все марки');
      cascade(modelListEl, facetMapToRows(maps.models), 'model', 'model', modelTrigger, 'Все модели');
      cascade(generationListEl, facetMapToRows(maps.generations), 'generation', 'generation', generationTrigger, 'Все поколения');
      cascade(trimListEl, facetMapToRows(maps.trims), 'trim', 'trim', trimTrigger, 'Все комплектации');
      renderFacetCheckboxList(document.getElementById('bodyList'), facetMapToRows(maps.body), 'body', 'bodyType');
      renderFacetCheckboxList(document.getElementById('fuelList'), facetMapToRows(maps.fuel), 'fuel', 'engineType');
      renderFacetCheckboxList(document.getElementById('transmissionList'), facetMapToRows(maps.trans), 'transmission', 'transmission');
      renderColorFilterFromFacets(facetMapToRows(maps.color));
      syncCascadeSlotVisibility();
      scheduleRepositionOpenCascadePanels();
    }

    async function refreshFacetBars(reqId) {
      const paramSnap = buildCatalogFilterParams().toString();
      if (useStaticCatalog && staticCatalogCache && staticCatalogCache.length) {
        refreshFacetsFromStaticCache(paramSnap);
        return;
      }
      if (facetsListAbort) {
        try {
          facetsListAbort.abort();
        } catch (eAb) {}
      }
      facetsListAbort = new AbortController();
      var sig = facetsListAbort.signal;
      var res;
      try {
        res = await fetch(apiUrl('/api/facets?' + paramSnap), catalogApiFetchInit({ signal: sig }));
      } catch (eFetch) {
        if (eFetch && eFetch.name === 'AbortError') return;
        throw eFetch;
      }
      if (!res.ok) throw new Error('facets HTTP ' + res.status);
      const data = await res.json();
      if (paramSnap !== buildCatalogFilterParams().toString()) return;
      applyFacetsApiPayload(data, reqId);
    }

    function markFacetsHydrated() {
      return !!(markListEl && markListEl.querySelector('input[type=checkbox]'));
    }

    /**
     * Снимок GET /api/facets без фильтров (frontend/data/catalog_facets.json с бэка).
     * Подмешиваем только пока список марок пуст — не перетираем свежий ответ API.
     */
    function prefetchStaticFacetsSnapshot(reqId) {
      syncCatalogMarketFromLocation();
      if (CATALOG_SOURCE !== 'encar' || CATALOG_REGION !== 'korea') return;
      if (useStaticCatalog && staticCatalogCache && staticCatalogCache.length) return;
      fetch('data/catalog_facets.json', { cache: 'default' })
        .then(function(r) { return r.ok ? r.json() : null; })
        .catch(function() { return null; })
        .then(function(data) {
          if (reqId !== catalogRequestId) return;
          if (markFacetsHydrated()) return;
          if (!data || typeof data !== 'object' || !Array.isArray(data.marks) || data.marks.length === 0) return;
          applyFacetsApiPayload(data, reqId);
        });
    }

    /** Дебаунс фасетов: быстрый выбор нескольких кузов/цветов → один запрос к API. */
    var facetDebounceTimer = null;
    var pendingFacetReqId = null;
    var FACET_DEBOUNCE_MS = 180;
    /** @param {boolean} [immediate] без задержки (первый заход, открытие drawer, clamp страницы). */
    function scheduleFacetRefresh(reqId, immediate) {
      function runFacet(rid) {
        refreshFacetBars(rid).catch(function(e) {
          if (e && e.name === 'AbortError') return;
          if (rid === catalogRequestId) console.warn('[catalog] facets failed', e);
        });
      }
      if (immediate) {
        if (facetDebounceTimer) {
          clearTimeout(facetDebounceTimer);
          facetDebounceTimer = null;
        }
        pendingFacetReqId = null;
        var rid0 = reqId;
        var run0 = function() {
          if (rid0 !== catalogRequestId) return;
          runFacet(rid0);
        };
        if (typeof queueMicrotask === 'function') queueMicrotask(run0);
        else setTimeout(run0, 0);
        return;
      }
      pendingFacetReqId = reqId;
      if (facetDebounceTimer) clearTimeout(facetDebounceTimer);
      facetDebounceTimer = setTimeout(function() {
        facetDebounceTimer = null;
        var rid = pendingFacetReqId;
        pendingFacetReqId = null;
        if (rid == null || rid !== catalogRequestId) return;
        runFacet(rid);
      }, FACET_DEBOUNCE_MS);
    }

    /** Короче ввод цены/пробега и т.д.; на change — немедленный apply; abort снимает гонки. */
    const APPLY_DEBOUNCE_MS = 120;
    let debouncedApplyTimer = null;
    function scheduleDebouncedApplyFilters() {
      if (debouncedApplyTimer) clearTimeout(debouncedApplyTimer);
      debouncedApplyTimer = setTimeout(function() {
        debouncedApplyTimer = null;
        void runApplyFilters();
      }, APPLY_DEBOUNCE_MS);
    }

    function flushDebouncedApplyAndRun() {
      if (debouncedApplyTimer) {
        clearTimeout(debouncedApplyTimer);
        debouncedApplyTimer = null;
      }
      void runApplyFilters();
    }

    function bindDebouncedNumericFilter(id) {
      var el = document.getElementById(id);
      if (!el) return;
      el.addEventListener('input', scheduleDebouncedApplyFilters);
      el.addEventListener('change', flushDebouncedApplyAndRun);
    }

    function parseCarsApiPayload(data) {
      var raw = null;
      if (data && Array.isArray(data.result)) raw = data.result;
      else if (data && Array.isArray(data.cars)) raw = data.cars;
      else if (data && Array.isArray(data.items)) raw = data.items;
      var list = Array.isArray(raw) ? raw : [];
      var seenIds = new Set();
      list = list.filter(function(c) {
        var d = c && (c.data || c);
        var enc = d && d.inner_id != null && String(d.inner_id).trim() !== '' ? String(d.inner_id).trim() : '';
        var key = enc ? ('enc:' + enc) : '';
        if (!key && c != null && c.id != null && String(c.id).trim() !== '') key = 'cid:' + String(c.id);
        if (!key) return true;
        if (seenIds.has(key)) return false;
        seenIds.add(key);
        return true;
      });
      var meta = data && data.meta && typeof data.meta === 'object' ? data.meta : {};
      var total = Number(meta.total);
      if (!Number.isFinite(total) || total < 0) total = 0;
      var perPage = Number(meta.per_page);
      if (!Number.isFinite(perPage) || perPage < 1) perPage = PER_PAGE;
      if (total === 0 && list.length > 0) total = list.length;
      var pages = Number(meta.pages);
      if (!Number.isFinite(pages) || pages < 1) {
        pages = total > 0 ? Math.max(1, Math.ceil(total / perPage)) : 1;
      }
      return { list: list, total: total, pages: pages };
    }

    function loadCarsPageStatic(targetPage, reqId) {
      if (!staticCatalogCache || !staticCatalogCache.length) return;
      if (reqId !== catalogRequestId) return;
      const params = buildCatalogFilterParams();
      let filtered = staticCatalogCache.filter(function(c) { return carMatchesParamsUrl(c, params); });
      filtered = dedupeCatalogCars(filtered);
      filtered = sortCarsStatic(filtered, currentSort || 'date_new');
      catalogTotal = filtered.length;
      catalogPages = Math.max(1, Math.ceil(catalogTotal / PER_PAGE));
      var tp = Math.max(1, Math.min(targetPage, catalogPages));
      page = tp;
      var start = (page - 1) * PER_PAGE;
      pageCars = filtered.slice(start, start + PER_PAGE);
      if (pageCars.length === 0 && catalogTotal > 0 && targetPage > 1) {
        page = 1;
        start = 0;
        pageCars = filtered.slice(0, PER_PAGE);
      }
      updateFilterCountBadge();
      draw();
    }

    function scheduleIdlePrefetchCatalogPage2() {
      if (useStaticCatalog || catalogPages < 2) return;
      try {
        if (buildCatalogFilterParamsSansDefaultSource().toString() !== '') return;
      } catch (e) {
        return;
      }
      function run() {
        try {
          var params = buildCatalogFilterParams();
          params.set('page', '2');
          params.set('per_page', String(PER_PAGE));
          params.set('sort', currentSort || 'date_new');
          var url = apiUrl('/api/cars?' + params.toString());
          var init = catalogApiFetchInit({});
          try {
            init.priority = 'low';
          } catch (e2) {}
          fetch(url, init).catch(function() {});
        } catch (e3) {}
      }
      if (typeof requestIdleCallback === 'function') {
        requestIdleCallback(run, { timeout: 5000 });
      } else {
        setTimeout(run, 2500);
      }
    }

    async function loadCarsPage(targetPage, reqId) {
      if (reqId == null) reqId = ++catalogRequestId;
      showSkeleton();
      if (useStaticCatalog && staticCatalogCache && staticCatalogCache.length) {
        loadCarsPageStatic(targetPage, reqId);
        return;
      }
      try {
        const params = buildCatalogFilterParams();
        params.set('page', String(targetPage));
        params.set('per_page', String(PER_PAGE));
        params.set('sort', currentSort || 'date_new');
        if (carsListAbort) {
          try {
            carsListAbort.abort();
          } catch (eCa) {}
        }
        carsListAbort = new AbortController();
        var carsTimeoutId = setTimeout(function() {
          try {
            carsListAbort.abort();
          } catch (eAb) {}
        }, CATALOG_CARS_TIMEOUT_MS);
        var res;
        try {
          res = await fetch(
            apiUrl('/api/cars?' + params.toString()),
            catalogApiFetchInit({ signal: carsListAbort.signal })
          );
        } catch (eF) {
          clearTimeout(carsTimeoutId);
          if (eF && eF.name === 'AbortError') return;
          throw eF;
        }
        clearTimeout(carsTimeoutId);
        if (!res.ok) throw new Error('cars HTTP ' + res.status);
        const data = await res.json();
        if (reqId !== catalogRequestId) return;
        const parsed = parseCarsApiPayload(data);
        pageCars = parsed.list;
        catalogTotal = parsed.total;
        catalogPages = parsed.pages;
        page = targetPage;
        maybeSyncMarketChinaCountFromCarsMeta(parsed.total);
        if (pageCars.length === 0 && catalogTotal > 0 && targetPage > 1) {
          await loadCarsPage(1, reqId);
          return;
        }
        updateFilterCountBadge();
        draw();
        if (targetPage === 1) scheduleIdlePrefetchCatalogPage2();
      } catch (err) {
        if (reqId !== catalogRequestId) return;
        if (err && err.name === 'AbortError') return;
        if (!staticCatalogCache && allowCarsJsonFallback()) {
          try {
            var jr = await fetch('cars.json');
            if (jr.ok) {
              var clHdr = jr.headers.get('Content-Length');
              if (clHdr) {
                var clNum = parseInt(clHdr, 10);
                if (clNum > CATALOG_JSON_FALLBACK_MAX_BYTES) {
                  throw new Error('cars.json too large (' + clNum + ' bytes) for in-browser fallback');
                }
              } else {
                throw new Error('cars.json: no Content-Length, skip parse (avoid tab OOM)');
              }
              var raw = await jr.json();
              var parsedInit = parseCarsApiPayload(raw);
              staticCatalogCache = dedupeCatalogCars(parsedInit.list);
              useStaticCatalog = true;
              loadCarsPageStatic(targetPage, reqId);
              scheduleFacetRefresh(reqId, true);
              return;
            }
          } catch (e2) { /* fall through */ }
        }
        console.error(err);
        pageCars = [];
        catalogTotal = 0;
        catalogPages = 1;
        var errMsg = 'Не удалось загрузить список объявлений.';
        if (err && err.message === 'timeout') errMsg = 'Сервер не ответил вовремя. Попробуйте ещё раз.';
        if (err && err.name === 'AbortError') errMsg = 'Запрос отменён или истекло время ожидания.';
        var emRaw = err && err.message != null ? String(err.message) : '';
        if (
          err &&
          err.name === 'TypeError' &&
          (/fetch|сеть|network|load failed|failed to fetch/i.test(emRaw) || emRaw === '')
        ) {
          errMsg =
            'API недоступен (нет ответа от /api/…). На сервере: запущен ли процесс с api_server, в nginx настроен ли proxy_pass для /api/ и совпадает ли WRA_API_BASE с реальным URL API.';
        }
        showCatalogErrorBanner(errMsg);
        if (paginationEl) paginationEl.innerHTML = '';
      }
    }

    async function runApplyFilters() {
      const reqId = ++catalogRequestId;
      page = 1;
      syncCascadeSlotVisibility();
      scheduleFacetRefresh(reqId);
      try {
        await loadCarsPage(1, reqId);
        if (reqId !== catalogRequestId) return;
      } catch (e) {
        if (reqId !== catalogRequestId) return;
        console.error(e);
        if (gridEl) {
          gridEl.setAttribute('aria-busy', 'false');
          gridEl.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; background:var(--wra-surface); border-radius:24px; border:1px solid var(--wra-border);"><p style="margin:0 0 16px;">Не удалось обновить каталог.</p><a href="/" class="btn btn-primary">Обновить страницу</a></div>';
        }
      }
    }

    function taxClass(yearStr) {
      const carYear = parseInt(String(yearStr).slice(0, 4));
      if (isNaN(carYear)) {
        return {
          cls: 'high',
          text: 'Высокая ставка',
          tooltip:
            '<strong>Возраст не определён</strong><br>' +
            'Год в объявлении не распознан. Метка условная — пошлины и сумму «под ключ» уточняйте у менеджера по VIN.'
        };
      }
      const now = new Date();
      const age = now.getFullYear() - carYear;
      if (age >= 3 && age < 5) {
        return {
          cls: 'pass',
          text: 'Проходной',
          tooltip:
            '<strong>Проходной возраст</strong><br>' +
            'По году в объявлении — <strong>3–4 года</strong>. Часто применяется <strong>более низкая ЕТС</strong>, чем у машин младше 3 лет. Итог — в расчёте карточки или у менеджера.'
        };
      }
      if (age < 3) {
        return {
          cls: 'high',
          text: 'Высокая ставка',
          tooltip:
            '<strong>Моложе 3 лет</strong><br>' +
            'По году модели <strong>меньше 3 лет</strong>. Нагрузка при ввозе обычно <strong>выше</strong>, чем у «проходных» 3–4 лет. Детали — в калькуляторе или у менеджера.'
        };
      }
      return {
        cls: 'high',
        text: 'Высокая ставка',
        tooltip:
          '<strong>5+ лет по году</strong><br>' +
          'Другие ставки и сборы — как правило <strong>менее выгодны</strong>, чем у 3–4 лет. Ориентир по объявлению; итог — у менеджера или в расчёте карточки.'
      };
    }

    function listingDedupeKeyForCatalog(car) {
      var d = car.data || car;
      var inner = d.inner_id != null && String(d.inner_id).trim() !== '' ? String(d.inner_id).trim() : '';
      if (inner) return 'i:' + inner;
      var cid = car.id != null ? String(car.id) : '';
      if (cid) return 'c:' + cid;
      return '';
    }

    /** Одна карточка на объявление Encar: в cars.json без дедупа могли быть дубликаты строк БД. */
    function dedupeCatalogCars(cars) {
      if (!Array.isArray(cars) || cars.length < 2) return cars;
      var seen = Object.create(null);
      var out = [];
      for (var i = 0; i < cars.length; i++) {
        var car = cars[i];
        var k = listingDedupeKeyForCatalog(car);
        if (!k) {
          out.push(car);
          continue;
        }
        if (seen[k]) continue;
        seen[k] = 1;
        out.push(car);
      }
      return out;
    }

    /** Номер кадра в URL Encar (…_012.jpg) — как на сайте источника; slim API раньше резал [:6] без сортировки. */
    function encarImageSeqFromUrl(url) {
      try {
        var base = typeof location !== 'undefined' && location.href ? location.href : 'https://rideauto.ru/';
        var u = new URL(String(url).trim(), base);
        var m = (u.pathname || '').match(/_(\d+)\.(?:jpe?g|png|webp)$/i);
        if (m) return parseInt(m[1], 10);
      } catch (e) {}
      var s = String(url || '');
      var m2 = s.match(/_(\d+)\.(?:jpe?g|png|webp)/i);
      return m2 ? parseInt(m2[1], 10) : 1e9;
    }

    function catalogThumbPenalty(url) {
      var u = String(url || '').toLowerCase();
      if (u.includes('wheel') || u.includes('tire') || u.includes('rim') || u.includes('диск')) return 1;
      if (u.includes('타이어') || u.includes('휠')) return 1;
      return 0;
    }

    function getPreviewImages(d) {
      var images = [];
      try { images = JSON.parse(d.images || '[]'); } catch (e) { images = []; }
      if (!Array.isArray(images) || !images.length) return [];
      var urls = images.filter(function(u) { return typeof u === 'string' && u.trim(); });
      var scored = urls.map(function(u) {
        return { u: u, seq: encarImageSeqFromUrl(u), pen: catalogThumbPenalty(u) };
      });
      scored.sort(function(a, b) {
        if (a.pen !== b.pen) return a.pen - b.pen;
        if (a.seq !== b.seq) return a.seq - b.seq;
        return a.u.localeCompare(b.u);
      });
      return scored.slice(0, 4).map(function(x) { return x.u; });
    }

    function escapeImgAttr(s) {
      return String(s)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;');
    }

    /** Encar CDN: второй вариант с увеличенными rh/cw/ch для DPR≈2 (как у pan-auto с impolicy). */
    function encarCatalogImageVariants(url) {
      try {
        var base = typeof location !== 'undefined' && location.href ? location.href : 'https://rideauto.ru/';
        var u = new URL(String(url || '').trim(), base);
        var hn = u.hostname.toLowerCase();
        if (!hn.endsWith('encar.com')) return null;
        var rhRaw = u.searchParams.get('rh');
        var cwRaw = u.searchParams.get('cw');
        if (rhRaw == null || cwRaw == null || rhRaw === '' || cwRaw === '') return null;
        var rhN = parseInt(rhRaw, 10);
        var cwN = parseInt(cwRaw, 10);
        if (!Number.isFinite(rhN) || !Number.isFinite(cwN) || cwN < 64) return null;
        var chRaw = u.searchParams.get('ch');
        var chN = chRaw != null && chRaw !== '' ? parseInt(chRaw, 10) : NaN;
        var scale = 2;
        var rh2 = Math.min(Math.round(rhN * scale), 960);
        var cw2 = Math.min(Math.round(cwN * scale), 1200);
        var ch2 = Number.isFinite(chN) ? Math.min(Math.round(chN * scale), 960) : null;
        var u2 = new URL(u.toString());
        u2.searchParams.set('rh', String(rh2));
        u2.searchParams.set('cw', String(cw2));
        if (ch2 != null) u2.searchParams.set('ch', String(ch2));
        return {
          srcset: escapeImgAttr(u.href) + ' ' + cwN + 'w, ' + escapeImgAttr(u2.href) + ' ' + cw2 + 'w',
          sizes: '(max-width: 640px) min(96vw, 560px), (max-width: 1100px) 42vw, 290px',
        };
      } catch (e) {
        return null;
      }
    }

    // Отрисовка карточек
    function draw() {
      if (!gridEl) return;
      gridEl.setAttribute('aria-busy', 'false');
      var totalN = Number(catalogTotal);
      if (!Number.isFinite(totalN) || totalN < 0) totalN = 0;
      if (totalN === 0) {
        var resetBtn = document.getElementById('resetFiltersBtn');
        var resetHtml = resetBtn ? '<button type="button" class="btn btn-primary" onclick="document.getElementById(\'resetFiltersBtn\').click()">Сбросить фильтры</button>' : '';
        gridEl.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; background:var(--wra-surface); border-radius:24px; border:1px solid var(--wra-border);"><p style="margin:0 0 16px;">Ничего не найдено. Попробуйте изменить фильтры.</p>' + resetHtml + '</div>';
        if (paginationEl) paginationEl.innerHTML = '';
        if (foundCounter) foundCounter.textContent = '0';
        if (catalogAriaLive) catalogAriaLive.textContent = 'Найдено 0 объявлений';
        return;
      }

      if (!pageCars || pageCars.length === 0) {
        gridEl.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; background:var(--wra-surface); border-radius:24px; border:1px solid var(--wra-border);"><p style="margin:0 0 16px;">Список не загрузился (есть ' + totalN.toLocaleString('ru-RU') + ' объявлений в базе). Обновите страницу.</p><a href="/" class="btn btn-primary">Обновить</a></div>';
        if (paginationEl) paginationEl.innerHTML = '';
        if (foundCounter) foundCounter.textContent = totalN.toLocaleString('ru-RU');
        if (catalogAriaLive) catalogAriaLive.textContent = 'Каталог не отобразился';
        return;
      }

      gridEl.innerHTML = '';
        const eagerHeroImage = page === 1;
        pageCars.forEach(function(car, cardIdx) {
        const d = car.data || car;
        const images = getPreviewImages(d);

        const card = document.createElement('div');
        card.className = 'car-card';

        const tax = taxClass(d.year);
        const iso = d.offer_created || d.created_at || '';
        const todayStr = new Date().toISOString().slice(0, 10);
        const isToday = String(iso).slice(0, 10) === todayStr;

        const titleMark = filterOptionLabel(d.mark, 'mark');
        const titleModel = filterOptionLabel(d.model, 'model');
        const titleGen = filterOptionLabel(d.generation || d.configuration, 'generation');
        const fullTitle = [titleMark, titleModel, titleGen].filter(Boolean).join(' ').trim() || (d.mark || '') + ' ' + (d.model || '');
        const powerNum = getPowerNum(car);
        const powerPart = powerNum ? `${powerNum} л.с.` : '';
        const fuelPart = filterOptionLabel(d.engine_type, 'engineType') || '';
        const volumePart = d.displacement ? `${Number(d.displacement).toLocaleString('ru-RU')} см³` : '';
        const drivePart = filterOptionLabel(d.drive_type || d.prep_drive_type, 'type') || '';
        const bodyRu = filterOptionLabel(d.body_type, 'bodyType') || '';
        const carUrl = (d.url || '#');
        card.innerHTML = `
          <div class="preview">
            ${isToday ? '<span class="card-badge card-badge-today">Добавлен сегодня</span>' : ''}
            ${images.map(function(img, i) {
              var hero = eagerHeroImage && cardIdx < 2 && i === 0;
              var attrs = hero
                ? 'fetchpriority="high" decoding="async"'
                : 'loading="lazy" decoding="async"';
              var enc = encarCatalogImageVariants(img);
              var srcEsc = escapeImgAttr(img);
              var rw = enc ? (' srcset="' + enc.srcset + '" sizes="' + enc.sizes + '"') : '';
              return '<img src="' + srcEsc + '"' + rw + ' alt="" class="' + (i === 0 ? 'active' : '') + '" width="290" height="186" ' + attrs + '>';
            }).join('')}
          </div>
          <div class="car-info">
            <div class="car-main">
              <div class="car-info-header">
                <h2>${fullTitle}</h2>
                <div class="car-actions">
                  <button type="button" class="icon-btn icon-btn--share" aria-label="Поделиться" title="Поделиться"><img src="image/External_Link.svg" alt="" width="18" height="18"></button>
                  <button type="button" class="icon-btn icon-btn--fav" aria-label="В избранное" title="В избранное"><img src="image/Heart_01.svg" alt="" width="18" height="18" class="fav-icon"></button>
                </div>
              </div>
              <div class="meta meta-strong">
                ${[powerPart, fuelPart, volumePart, formatKm(d.km_age)].filter(Boolean).join(', ')}
              </div>
              <div class="meta">
                ${formatYear(d.year)} • ${bodyRu}${drivePart ? ', привод ' + drivePart : ''}
              </div>
            </div>
            <div class="price-row">
              <div class="price-block-inline">
                <span class="price-rub ${(d.my_price == null || d.my_price === '' || d.price_calc_failed) ? 'price-rub-fallback' : ''}" ${(d.my_price == null || d.my_price === '' || d.price_calc_failed) && (d.price_calc_failed || d.price_won) ? ' title="Обратитесь к менеджеру для просчёта"' : ''}>
                  ${(d.my_price != null && d.my_price !== '' && !d.price_calc_failed) ? Math.round(Number(d.my_price)).toLocaleString() + ' ₽' : ((d.price_calc_failed || (d.price_won != null && (d.my_price == null || d.my_price === ''))) ? 'Цена по запросу' : '—')}
                </span>
                <span class="delivery-line">до Владивостока <span class="info-icon-wrap" title="Доставка до Владивостока"><img src="image/Info.svg" alt="i" width="12" height="12" class="info-icon-img"></span></span>
              </div>
              <a href="${carUrl}" target="_blank" rel="noopener noreferrer" class="tax-btn ${tax.cls}">${tax.text}</a>
            </div>
          </div>
        `;

        // Переключение фото движением курсора
        const preview = card.querySelector('.preview');
        if (preview) {
          const imgs = Array.from(preview.querySelectorAll('img'));
          preview.addEventListener('mousemove', (e) => {
            if (imgs.length <= 1) return;
            const w = preview.offsetWidth;
            const pos = e.offsetX / w;
            const idx = Math.min(Math.floor(pos * imgs.length), imgs.length - 1);
            imgs.forEach((img, k) => img.classList.toggle('active', k === idx));
          });
          preview.addEventListener('mouseleave', () => {
            imgs.forEach((img, k) => img.classList.toggle('active', k === 0));
          });
        }

        // Тултип для кнопки ставки (тёмный полупрозрачный, плавное появление)
        const btn = card.querySelector('.tax-btn');
        if (btn) {
          const btnTooltip = document.createElement('div');
          btnTooltip.className = 'tooltip tooltip--catalog-tax';
          btnTooltip.innerHTML = tax.tooltip;
          document.body.appendChild(btnTooltip);
          btn.addEventListener('mouseenter', function() { showCatalogTaxTooltip(btnTooltip, btn.getBoundingClientRect()); });
          btn.addEventListener('mouseleave', function() { hideCatalogTaxTooltip(btnTooltip); });
          btn.addEventListener('focus', function() { showCatalogTaxTooltip(btnTooltip, btn.getBoundingClientRect()); });
          btn.addEventListener('blur', function() { hideCatalogTaxTooltip(btnTooltip); });
        }

        // Тултип для info-icon (иконка «i» у «до Владивостока»)
        const info = card.querySelector('.delivery-line .info-icon-wrap');
        if (info) {
          const infoTooltip = document.createElement('div');
          infoTooltip.className = 'tooltip';
          infoTooltip.innerHTML = 'Доставка до Владивостока. Срок и стоимость уточняйте у менеджера.';
          document.body.appendChild(infoTooltip);
          info.addEventListener('mouseenter', () => { positionTooltip(infoTooltip, info.getBoundingClientRect()); });
          info.addEventListener('mouseleave', () => { infoTooltip.style.display = 'none'; });
        }

        // Поделиться — копировать ссылку и показать «Ссылка скопирована»
        const shareBtn = card.querySelector('.car-actions .icon-btn--share');
        bindCardIconPressSpring(shareBtn);
        if (shareBtn) shareBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          navigator.clipboard.writeText(carUrl).then(() => {
            var toast = document.getElementById('toastLinkCopied');
            if (!toast) {
              toast = document.createElement('div');
              toast.id = 'toastLinkCopied';
              toast.className = 'toast-link-copied';
              toast.textContent = 'Ссылка скопирована';
              document.body.appendChild(toast);
            }
            toast.classList.add('show');
            clearTimeout(shareBtn._toastTimer);
            shareBtn._toastTimer = setTimeout(() => { toast.classList.remove('show'); }, 2000);
          }).catch(() => { window.open(carUrl, '_blank'); });
        });
        // Избранное — переключение состояния
        const favBtn = card.querySelector('.car-actions .icon-btn--fav');
        bindCardIconPressSpring(favBtn);
        if (favBtn) {
          const sid = car.id != null ? car.id : (car.inner_id != null ? car.inner_id : (car.data && car.data.inner_id != null ? car.data.inner_id : null));
          if (window.WRAAuthFavorites && typeof window.WRAAuthFavorites.bindFavoriteButton === 'function' && sid != null) {
            window.WRAAuthFavorites.bindFavoriteButton(favBtn, sid);
          } else {
            favBtn.addEventListener('click', (e) => {
              e.stopPropagation();
              favBtn.classList.toggle('fav-active');
            });
          }
        }
        // Клик по карточке для перехода на детальную страницу
        card.setAttribute('role', 'link');
        card.setAttribute('tabindex', '0');
        card.setAttribute('aria-label', 'Перейти к карточке ' + fullTitle);
        function goToCar(linkId) {
            try {
                sessionStorage.setItem('encar_catalog_scroll', String(window.scrollY || document.documentElement.scrollTop));
                sessionStorage.setItem('encar_catalog_page', String(page));
            } catch (e) {}
            window.location.href = typeof window.wraCarDetailUrl === 'function'
              ? window.wraCarDetailUrl(linkId)
              : ('/detail/' + encodeURIComponent(linkId));
        }
        card.addEventListener('click', (e) => {
            if (e.target.closest('a') || e.target.closest('button') || e.target.closest('.info-icon-wrap') || e.target.closest('.car-actions')) return;
            const linkId = car.id != null ? car.id : (car.inner_id != null ? car.inner_id : (car.data && car.data.inner_id != null ? car.data.inner_id : null));
            if (linkId == null) return;
            goToCar(linkId);
        });
        card.addEventListener('keydown', function(e) {
          if (e.key === 'Enter' && !e.target.closest('a') && !e.target.closest('button')) {
            e.preventDefault();
            var linkId = car.id != null ? car.id : (car.inner_id != null ? car.inner_id : (car.data && car.data.inner_id != null ? car.data.inner_id : null));
            if (linkId != null) goToCar(linkId);
          }
        });

        gridEl.appendChild(card);
      });

      drawPagination();
      if (foundCounter) foundCounter.textContent = totalN.toLocaleString('ru-RU');
      if (catalogAriaLive) catalogAriaLive.textContent = 'Найдено ' + totalN.toLocaleString('ru-RU') + ' объявлений';
    }

    function drawPagination() {
      if (!paginationEl) return;
      const total = catalogPages;
      paginationEl.innerHTML = '';
      if (total <= 1) return;

      const go = (p) => {
        void loadCarsPage(p);
        window.scrollTo({ top: 0, behavior: 'smooth' });
      };

      const nav = document.createElement('nav');
      nav.className = 'pagination';
      nav.setAttribute('aria-label', 'Pagination navigation');
      const list = document.createElement('ul');
      list.className = 'pagination__list';
      list.setAttribute('role', 'list');
      nav.appendChild(list);

      const makeItem = () => {
        const li = document.createElement('li');
        li.className = 'pagination__item';
        return li;
      };
      const makeArrow = (dir, disabled, targetPage) => {
        const li = makeItem();
        const a = document.createElement('a');
        a.href = '#';
        a.className = 'pagination__link pagination__link--arrow' + (disabled ? ' pagination__link--disabled' : '');
        a.setAttribute('aria-label', dir === 'prev' ? 'Previous' : 'Next');
        if (disabled) a.setAttribute('aria-disabled', 'true');
        a.innerHTML = dir === 'prev'
          ? '<svg width="8" height="12" viewBox="0 0 8 12" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M7 11L2 6L7 1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path></svg>'
          : '<svg width="8" height="12" viewBox="0 0 8 12" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M1 1L6 6L1 11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path></svg>';
        a.addEventListener('click', (e) => {
          e.preventDefault();
          if (!disabled) go(targetPage);
        });
        li.appendChild(a);
        return li;
      };
      const makePage = (p) => {
        const li = makeItem();
        const a = document.createElement('a');
        a.href = '#';
        a.className = 'pagination__link' + (p === page ? ' pagination__link--current' : '');
        a.setAttribute('aria-label', `Page ${p}`);
        if (p === page) a.setAttribute('aria-current', 'page');
        a.textContent = String(p);
        a.addEventListener('click', (e) => {
          e.preventDefault();
          if (p !== page) go(p);
        });
        li.appendChild(a);
        return li;
      };
      const makeGap = (mobileOnly) => {
        const li = makeItem();
        li.className += ' pagination__gap' + (mobileOnly ? ' pagination__item--mobile-only' : '');
        const s = document.createElement('span');
        s.className = 'pagination__link--gap';
        s.setAttribute('aria-hidden', 'true');
        s.textContent = '…';
        li.appendChild(s);
        return li;
      };

      list.appendChild(makeArrow('prev', page <= 1, Math.max(1, page - 1)));

      const maxVisible = window.innerWidth <= 600 ? 5 : 7;
      let from = Math.max(1, page - Math.floor((maxVisible - 1) / 2));
      let to = Math.min(total, from + maxVisible - 1);
      if (to - from + 1 < maxVisible) from = Math.max(1, to - maxVisible + 1);

      if (from > 1) {
        list.appendChild(makePage(1));
        if (from > 2) list.appendChild(makeGap(window.innerWidth <= 600));
      }
      for (let i = from; i <= to; i++) list.appendChild(makePage(i));
      if (to < total) {
        if (to < total - 1) list.appendChild(makeGap(window.innerWidth <= 600));
        list.appendChild(makePage(total));
      }

      list.appendChild(makeArrow('next', page >= total, Math.min(total, page + 1)));
      paginationEl.appendChild(nav);

      const updateActiveIndicator = () => {
        const active = list.querySelector('.pagination__link[aria-current="page"]');
        if (!active) {
          list.classList.remove('has-active');
          return;
        }
        const listRect = list.getBoundingClientRect();
        const activeRect = active.getBoundingClientRect();
        list.style.setProperty('--active-x', (activeRect.left - listRect.left) + 'px');
        list.style.setProperty('--active-y', (activeRect.top - listRect.top) + 'px');
        list.style.setProperty('--active-w', activeRect.width + 'px');
        list.style.setProperty('--active-h', activeRect.height + 'px');
        list.classList.add('has-active');
      };
      requestAnimationFrame(updateActiveIndicator);
    }

    // ---------- Построение фильтров на основе данных ----------
    const MONTHS = ['', '01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'];
    const MONTH_LABELS = ['', 'Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'];

    function syncYearMonthDropdowns() {
      var yearFromEl = document.getElementById('yearFrom');
      var yearToEl = document.getElementById('yearTo');
      var monthFromEl = document.getElementById('monthFrom');
      var monthToEl = document.getElementById('monthTo');
      var cap = new Date();
      var cy = cap.getFullYear();
      var cm = cap.getMonth() + 1;
      function refillMonths(sel, placeholder, yearVal) {
        if (!sel) return;
        var prev = sel.value;
        var y = parseInt(yearVal, 10);
        var maxM = 12;
        if (!Number.isNaN(y) && y === cy) maxM = cm;
        sel.innerHTML = '<option value="">' + placeholder + '</option>';
        for (var m = 1; m <= maxM; m++) {
          var o = document.createElement('option');
          o.value = MONTHS[m];
          o.textContent = MONTH_LABELS[m];
          sel.appendChild(o);
        }
        if (prev) {
          var pm = parseInt(prev, 10);
          if (!Number.isNaN(pm) && pm >= 1 && pm <= maxM) sel.value = MONTHS[pm];
          else sel.value = '';
        } else sel.value = '';
      }
      refillMonths(monthFromEl, 'Месяц от', yearFromEl && yearFromEl.value);
      refillMonths(monthToEl, 'Месяц до', yearToEl && yearToEl.value);
      syncCustomSelectUi(monthFromEl, monthFromTrigger, monthFromOptions, 'Месяц от');
      syncCustomSelectUi(monthToEl, monthToTrigger, monthToOptions, 'Месяц до');
    }

    function initCatalogFiltersUi() {
      const yearFromEl = document.getElementById('yearFrom');
      const yearToEl = document.getElementById('yearTo');
      const monthFromEl = document.getElementById('monthFrom');
      const monthToEl = document.getElementById('monthTo');
      var capY = new Date().getFullYear();
      [yearFromEl, yearToEl].forEach(function(sel) {
        if (!sel) return;
        sel.innerHTML = '<option value="">' + (sel.id === 'yearFrom' ? 'Год от' : 'Год до') + '</option>';
        for (var y = capY; y >= 1980; y--) {
          var o = document.createElement('option');
          o.value = y;
          o.textContent = y;
          sel.appendChild(o);
        }
      });
      bindCustomSelectDropdown(yearFromEl, yearFromTrigger, yearFromPanel, yearFromOptions, 'Год от');
      bindCustomSelectDropdown(yearToEl, yearToTrigger, yearToPanel, yearToOptions, 'Год до');
      syncYearMonthDropdowns();
      bindCustomSelectDropdown(monthFromEl, monthFromTrigger, monthFromPanel, monthFromOptions, 'Месяц от');
      bindCustomSelectDropdown(monthToEl, monthToTrigger, monthToPanel, monthToOptions, 'Месяц до');

      var filtersPanelEl = document.getElementById('filtersPanel');
      if (filtersPanelEl && !filtersPanelEl.dataset.wraFilterDelegate) {
        filtersPanelEl.dataset.wraFilterDelegate = '1';
        filtersPanelEl.addEventListener('change', function(e) {
          var t = e.target;
          if (!t || t.type !== 'checkbox') return;
          var df = t.getAttribute('data-filter');
          if (df === 'mark' || df === 'model' || df === 'generation' || df === 'trim') return;
          if (df === 'color') {
            syncAllColorCheckboxStates();
            updateFilterCountBadge();
            void runApplyFilters();
            return;
          }
          if (t.id === 'filterPassageCars') {
            void runApplyFilters();
            return;
          }
          if (
            df === 'noInsuranceCases' ||
            df === 'noInsurancePayouts' ||
            df === 'noDamaged' ||
            t.id === 'filterNoInsuranceCases' ||
            t.id === 'filterNoInsurancePayouts' ||
            t.id === 'filterNoDamaged'
          ) {
            void runApplyFilters();
            return;
          }
          if (t.closest('#bodyList') || t.closest('#fuelList') || t.closest('#transmissionList') || t.closest('.drive-checkbox-wrap')) {
            void runApplyFilters();
          }
        });
      }

      CASCADE_DROPDOWN_PAIRS.forEach(function(pair) {
        var btn = pair[0], panel = pair[1];
        if (!btn || !panel) return;
        btn.addEventListener('click', function(e) {
          if (e.target && e.target.closest('.ms-tag-remove')) return;
          e.stopPropagation();
          if (btn.disabled) return;
          var isOpen = panel.classList.contains('is-open');
          closeAllDropdowns();
          if (!isOpen) {
            panel.classList.add('is-open');
            btn.classList.add('active');
            btn.setAttribute('aria-expanded', 'true');
            requestAnimationFrame(function() {
              requestAnimationFrame(function() {
                dockOpenCascadePanel(btn, panel);
              });
            });
          }
        });
      });
      window.addEventListener('scroll', scheduleRepositionOpenCascadePanels, { capture: true, passive: true });
      window.addEventListener('resize', scheduleRepositionOpenCascadePanels, { passive: true });
      var filtersScroll = document.querySelector('.filters-panel-scroll');
      if (filtersScroll && !filtersScroll.dataset.wraCascadeScrollBound) {
        filtersScroll.dataset.wraCascadeScrollBound = '1';
        filtersScroll.addEventListener('scroll', scheduleRepositionOpenCascadePanels, { passive: true });
      }
      document.addEventListener('click', function(e) {
        if (e.target.closest('.filter-dropdown')) return;
        closeAllDropdowns();
      });

      if (markListEl) {
        markListEl.addEventListener('change', function(e) {
          if (!e.target || e.target.getAttribute('data-filter') !== 'mark') return;
          closeAllDropdowns();
          clearFacetCheckboxes(modelListEl);
          clearFacetCheckboxes(generationListEl);
          clearFacetCheckboxes(trimListEl);
          setDropdownTriggerText(markTrigger, markListEl, 'mark', 'Все марки');
          setDropdownTriggerText(modelTrigger, modelListEl, 'model', 'Все модели');
          setDropdownTriggerText(generationTrigger, generationListEl, 'generation', 'Все поколения');
          setDropdownTriggerText(trimTrigger, trimListEl, 'trim', 'Все комплектации');
          syncCascadeSlotVisibility();
          void runApplyFilters();
        });
      }
      if (modelListEl) {
        modelListEl.addEventListener('change', function(e) {
          if (!e.target || e.target.getAttribute('data-filter') !== 'model') return;
          closeAllDropdowns();
          clearFacetCheckboxes(generationListEl);
          clearFacetCheckboxes(trimListEl);
          setDropdownTriggerText(modelTrigger, modelListEl, 'model', 'Все модели');
          setDropdownTriggerText(generationTrigger, generationListEl, 'generation', 'Все поколения');
          setDropdownTriggerText(trimTrigger, trimListEl, 'trim', 'Все комплектации');
          syncCascadeSlotVisibility();
          void runApplyFilters();
        });
      }
      if (generationListEl) {
        generationListEl.addEventListener('change', function(e) {
          if (!e.target || e.target.getAttribute('data-filter') !== 'generation') return;
          closeAllDropdowns();
          clearFacetCheckboxes(trimListEl);
          setDropdownTriggerText(generationTrigger, generationListEl, 'generation', 'Все поколения');
          setDropdownTriggerText(trimTrigger, trimListEl, 'trim', 'Все комплектации');
          syncCascadeSlotVisibility();
          void runApplyFilters();
        });
      }
      if (trimListEl) {
        trimListEl.addEventListener('change', function(e) {
          if (!e.target || e.target.getAttribute('data-filter') !== 'trim') return;
          closeAllDropdowns();
          setDropdownTriggerText(trimTrigger, trimListEl, 'trim', 'Все комплектации');
          syncCascadeSlotVisibility();
          void runApplyFilters();
        });
      }

      ['powerFrom', 'powerTo', 'engineFrom', 'engineTo', 'priceFrom', 'priceTo', 'mileageFrom', 'mileageTo',
        'insuranceCasesFrom', 'insuranceCasesTo', 'insurancePayoutsFrom', 'insurancePayoutsTo', 'damagedFrom', 'damagedTo'].forEach(bindDebouncedNumericFilter);
      [yearFromEl, yearToEl].filter(Boolean).forEach(function(el) {
        el.addEventListener('change', function() {
          syncYearMonthDropdowns();
          void runApplyFilters();
        });
      });
      [monthFromEl, monthToEl].filter(Boolean).forEach(function(el) {
        el.addEventListener('change', function() { void runApplyFilters(); });
      });
      syncCheckboxVisualStates(document);

      initFilterSectionToggles();

      syncCascadeSlotVisibility();

      document.addEventListener('change', function(e) {
        var t = e.target;
        if (!t || t.type !== 'checkbox' || t.getAttribute('data-filter') !== 'color') return;
        if (!t.closest('#colorModalList')) return;
        syncAllColorCheckboxStates();
        updateFilterCountBadge();
        void runApplyFilters();
      });
    }

    function escapeHtml(s) {
      const div = document.createElement('div');
      div.textContent = String(s == null ? '' : s);
      return div.innerHTML;
    }

    function getSelectedValues(container, filterKey) {
      const out = new Set();
      if (!container) return out;
      container.querySelectorAll('input[type=checkbox][data-filter="' + filterKey + '"]:checked').forEach(function(cb) {
        expandFacetCheckboxValues(cb).forEach(function(v) { out.add(v); });
      });
      return out;
    }
    function clearFacetCheckboxes(container) {
      if (!container) return;
      container.querySelectorAll('input[type=checkbox]').forEach(function(cb) { cb.checked = false; });
    }
    function syncAllColorCheckboxStates() {
      var byValue = {};
      document.querySelectorAll('input[data-filter="color"]').forEach(function(cb) {
        if (byValue[cb.value] === undefined) byValue[cb.value] = false;
        byValue[cb.value] = byValue[cb.value] || cb.checked;
      });
      document.querySelectorAll('input[data-filter="color"]').forEach(function(cb) {
        cb.checked = !!byValue[cb.value];
      });
      syncCheckboxVisualStates(document);
    }

    function closeFilterDropdownPair(trigger, panel) {
      if (!trigger || !panel) return;
      if (panel.classList.contains('is-open')) {
        panel.classList.remove('filter-dropdown-panel--floating');
        ['--wra-float-left', '--wra-float-top', '--wra-float-width', '--wra-float-max-height'].forEach(function(prop) {
          panel.style.removeProperty(prop);
        });
        panel.classList.remove('is-open');
        trigger.classList.remove('active');
        trigger.setAttribute('aria-expanded', 'false');
      }
    }

    function syncCascadeSlotVisibility() {
      var marks = getSelectedValues(markListEl, 'mark');
      var models = getSelectedValues(modelListEl, 'model');
      var gens = getSelectedValues(generationListEl, 'generation');
      var slotModel = document.getElementById('cascadeSlotModel');
      var slotGen = document.getElementById('cascadeSlotGeneration');
      var slotTrim = document.getElementById('cascadeSlotTrim');
      if (slotModel) {
        var showM = marks.size > 0;
        slotModel.classList.toggle('is-revealed', showM);
        slotModel.setAttribute('aria-hidden', showM ? 'false' : 'true');
      }
      if (slotGen) {
        var showG = marks.size > 0 && models.size > 0;
        slotGen.classList.toggle('is-revealed', showG);
        slotGen.setAttribute('aria-hidden', showG ? 'false' : 'true');
      }
      if (slotTrim) {
        var showT = marks.size > 0 && models.size > 0 && gens.size > 0;
        slotTrim.classList.toggle('is-revealed', showT);
        slotTrim.setAttribute('aria-hidden', showT ? 'false' : 'true');
      }
      if (modelTrigger) {
        modelTrigger.disabled = marks.size === 0;
        if (marks.size === 0) {
          modelTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите марку</span>';
        }
      }
      if (generationTrigger) {
        var disG = marks.size === 0 || models.size === 0;
        generationTrigger.disabled = disG;
        if (disG) {
          generationTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите модель</span>';
        }
      }
      if (trimTrigger) {
        var disT = marks.size === 0 || models.size === 0 || gens.size === 0;
        trimTrigger.disabled = disT;
        if (disT) {
          trimTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите поколение</span>';
        }
      }
    }

    function initFilterSectionToggles() {
      function bindToggle(btnId, wrapId, bodyId) {
        const btn = document.getElementById(btnId);
        const wrap = document.getElementById(wrapId);
        const body = document.getElementById(bodyId);
        if (!btn || !wrap || !body || btn._wraFilterSectionBound) return;
        btn._wraFilterSectionBound = true;
        btn.addEventListener('click', function() {
          const open = !wrap.classList.contains('is-open');
          wrap.classList.toggle('is-open', open);
          btn.setAttribute('aria-expanded', open ? 'true' : 'false');
          body.setAttribute('aria-hidden', open ? 'false' : 'true');
        });
      }
      bindToggle('filterSectionTechBtn', 'filterSectionTech', 'filterSectionTechBody');
      bindToggle('filterSectionHistoryBtn', 'filterSectionHistory', 'filterSectionHistoryBody');
    }

    function renderCheckboxesWithCounts(container, mergedRows, labelCategory, filterKey) {
      if (!container) return;
      container.innerHTML = '';
      (mergedRows || []).forEach(function(row, idx) {
        const div = document.createElement('div');
        div.className = 'checkbox-item';
        const val = row.value;
        const variants = row.variants && row.variants.length ? row.variants : [val];
        const id = 'filter-' + filterKey + '-' + idx + '-' + String(val).replace(/\s/g, '_').replace(/[^\w\-]/g, '_');
        const label = labelCategory ? filterOptionLabel(val, labelCategory) : val;
        const cnt = row.count != null ? row.count : null;
        const suffix = (cnt != null) ? (' <span class="opt-count">(' + Number(cnt).toLocaleString('ru-RU') + ')</span>') : '';
        div.innerHTML = checkboxTemplate(id, filterKey, escapeHtml(val), escapeHtml(label) + suffix, variants);
        container.appendChild(div);
      });
      syncCheckboxVisualStates(container);
    }

    // Сброс всех фильтров
    function resetFilters() {
      closeAllDropdowns();
      [markListEl, modelListEl, generationListEl, trimListEl].forEach(function(container) {
        if (container) container.querySelectorAll('input[type=checkbox]').forEach(function(cb) { cb.checked = false; });
      });
      if (markTrigger) markTrigger.innerHTML = '<span class="trigger-placeholder">Все марки</span>';
      document.querySelectorAll('#bodyList input[type=checkbox], #fuelList input[type=checkbox], #transmissionList input[type=checkbox], .drive-checkbox-wrap input[type=checkbox]').forEach(function(cb) { cb.checked = false; });
      document.querySelectorAll('input[data-filter="color"]').forEach(function(cb) { cb.checked = false; });
      var ids = ['powerFrom', 'powerTo', 'engineFrom', 'engineTo', 'yearFrom', 'monthFrom', 'yearTo', 'monthTo', 'priceFrom', 'priceTo', 'mileageFrom', 'mileageTo', 'insuranceCasesFrom', 'insuranceCasesTo', 'insurancePayoutsFrom', 'insurancePayoutsTo', 'damagedFrom', 'damagedTo'];
      ids.forEach(function(id) { var el = document.getElementById(id); if (el) el.value = ''; });
      var pr = document.getElementById('priceRubTo'); if (pr) pr.value = '';
      var chk = document.getElementById('filterDriveAwd'); if (chk) chk.checked = false;
      chk = document.getElementById('filterNoInsuranceCases'); if (chk) chk.checked = false;
      chk = document.getElementById('filterNoInsurancePayouts'); if (chk) chk.checked = false;
      chk = document.getElementById('filterNoDamaged'); if (chk) chk.checked = false;
      chk = document.getElementById('filterPassageCars'); if (chk) chk.checked = false;
      syncCheckboxVisualStates(document);
      syncCascadeSlotVisibility();
      void runApplyFilters();
    }

    showSkeleton();

    var mappingPromise = fetch('data/encar_mapping.json', { cache: 'default' })
      .then(function(r) { return r.ok ? r.json() : null; })
      .catch(function() { return null; });

    mappingPromise.then(function(mapping) {
      if (mapping && typeof mapping === 'object') {
        ['mark', 'model', 'generation', 'type', 'trim'].forEach(function(cat) {
          if (mapping[cat] && typeof mapping[cat] === 'object') {
            filterMappingKoEn[cat] = Object.assign({}, mapping[cat], filterMappingKoEn[cat] || {});
          }
        });
      }
    }).catch(function() {});

    async function bootstrapCatalog() {
      try {
        syncCatalogMarketFromLocation();
        applyCatalogRegionUi();
        initCatalogFiltersUi();

        var savedScroll = null;
        var savedPage = null;
        try {
          savedScroll = sessionStorage.getItem('encar_catalog_scroll');
          savedPage = sessionStorage.getItem('encar_catalog_page');
          if (savedScroll !== null || savedPage !== null) {
            sessionStorage.removeItem('encar_catalog_scroll');
            sessionStorage.removeItem('encar_catalog_page');
          }
        } catch (e) {}

        var wantPage = 1;
        if (savedPage !== null) {
          var pageNum = Math.max(1, parseInt(savedPage, 10));
          if (!isNaN(pageNum)) wantPage = pageNum;
        }

        var reqId = ++catalogRequestId;
        var todayEl = document.getElementById('bannerTodayCount');
        var marketKoreaEl = document.getElementById('marketKoreaCount');
        var marketChinaEl = document.getElementById('marketChinaCount');
        var needStats = !!(todayEl || marketKoreaEl || marketChinaEl);
        var statsPromise = needStats
          ? withTimeout(
              fetch(apiUrl('/api/counts'), catalogApiFetchInit())
                .then(function(cr) {
                  if (cr.ok) return cr.json();
                  return fetch(apiUrl('/api/stats'), catalogApiFetchInit()).then(function(sr) {
                    if (!sr.ok) throw new Error('stats HTTP ' + sr.status);
                    return sr.json();
                  });
                })
                .catch(function() {
                  return fetch(apiUrl('/api/stats'), catalogApiFetchInit())
                    .then(function(sr) {
                      return sr.ok ? sr.json() : null;
                    })
                    .catch(function() {
                      return null;
                    });
                }),
              CATALOG_STATS_TIMEOUT_MS,
              'timeout'
            ).catch(function() {
              return null;
            })
          : Promise.resolve(null);

        function fmtMarketListedCount(n) {
          if (n == null || n === '') return '—';
          var num = typeof n === 'number' ? n : Number(String(n).replace(/[^\d.-]/g, ''));
          if (!Number.isFinite(num) || num < 0) return '—';
          return Math.round(num).toLocaleString('ru-RU');
        }

        function applyCatalogStatsPayload(st) {
          if (!needStats) return;
          try {
            if (todayEl) {
              var n0 = (st && typeof st.listed_today === 'number') ? st.listed_today : 0;
              todayEl.textContent = n0 > 0 ? ('+' + n0.toLocaleString('ru-RU')) : '+0';
            }
            if (marketKoreaEl) marketKoreaEl.textContent = fmtMarketListedCount(st && st.korea_listed);
            if (marketChinaEl) marketChinaEl.textContent = fmtMarketListedCount(st && st.china_listed);
          } catch (eApply) {
            if (todayEl) todayEl.textContent = '+0';
            if (marketKoreaEl) marketKoreaEl.textContent = '—';
            if (marketChinaEl) marketChinaEl.textContent = '—';
          }
        }

        if (needStats) {
          void statsPromise.then(function(st) {
            applyCatalogStatsPayload(st);
          });
        }

        prefetchStaticFacetsSnapshot(reqId);
        scheduleFacetRefresh(reqId, true);
        var facetBootstrapId = reqId;
        await loadCarsPage(wantPage, reqId);
        if (reqId !== catalogRequestId) return;
        if (wantPage > catalogPages && catalogPages >= 1) {
          facetBootstrapId = ++catalogRequestId;
          await loadCarsPage(catalogPages, facetBootstrapId);
          if (facetBootstrapId !== catalogRequestId) return;
          if (facetBootstrapId !== reqId) {
            prefetchStaticFacetsSnapshot(facetBootstrapId);
            scheduleFacetRefresh(facetBootstrapId, true);
          }
        }

        if (needStats) {
          try {
            await statsPromise;
          } catch (eAwaitStats) {
            /* UI уже заполнен через .then или останется «—» / +0 */
          }
        }

        if (savedScroll !== null) {
          var scrollY = parseInt(savedScroll, 10);
          if (!isNaN(scrollY) && scrollY > 0) {
            requestAnimationFrame(function() {
              requestAnimationFrame(function() { window.scrollTo(0, scrollY); });
            });
          }
        }
      } catch (err) {
        console.error('Ошибка загрузки каталога', err);
        showCatalogErrorBanner(
          'Не удалось загрузить каталог. Проверьте, что API доступен по тому же домену (например /api/cars).'
        );
      }
    }
    window.WRA_runCatalogBootstrap = bootstrapCatalog;
    bootstrapCatalog();

    var resetFiltersBtn = document.getElementById('resetFiltersBtn');
    if (resetFiltersBtn) {
      resetFiltersBtn.addEventListener('click', resetFilters);
      var pressResetSpring = null;
      function playPressSpring() {
        if (!resetFiltersBtn.animate) return;
        if (pressResetSpring) try { pressResetSpring.cancel(); } catch (e1) {}
        pressResetSpring = resetFiltersBtn.animate(
          [{ transform: 'scale(1)' }, { transform: 'scale(0.94)' }],
          { duration: 85, easing: 'cubic-bezier(0.32, 0, 0.67, 0)' }
        );
        pressResetSpring.onfinish = function() {
          resetFiltersBtn.animate(
            [{ transform: 'scale(0.94)' }, { transform: 'scale(1)' }],
            { duration: 420, easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)' }
          );
        };
      }
      resetFiltersBtn.addEventListener('pointerdown', playPressSpring);
    }

    // Модальное окно «Показать цвета ещё»
    const colorModalOverlay = document.getElementById('colorModalOverlay');
    const showMoreColorsBtn = document.getElementById('showMoreColorsBtn');
    const colorModalClose = document.getElementById('colorModalClose');
    if (showMoreColorsBtn) {
      showMoreColorsBtn.addEventListener('click', function() {
        if (colorModalOverlay) {
          var panel = document.getElementById('filtersPanel');
          var mx = 0;
          var my = 0;
          if (panel) {
            var r = panel.getBoundingClientRect();
            mx = (r.left + r.width / 2) - window.innerWidth / 2;
            my = (r.top + r.height / 2) - window.innerHeight / 2;
          }
          colorModalOverlay.style.setProperty('--color-modal-dx', mx + 'px');
          colorModalOverlay.style.setProperty('--color-modal-dy', my + 'px');
          colorModalOverlay.classList.add('is-open');
          document.querySelectorAll('#colorListVisible input[data-filter="color"]').forEach(function(visCb) {
            var v = visCb.value;
            document.querySelectorAll('#colorModalList input[data-filter="color"]').forEach(function(modalCb) {
              if (modalCb.value === v) modalCb.checked = visCb.checked;
            });
          });
        }
      });
    }
    if (colorModalClose) colorModalClose.addEventListener('click', function() { colorModalOverlay.classList.remove('is-open'); });
    if (colorModalOverlay) {
      colorModalOverlay.addEventListener('click', function(e) {
        if (e.target === colorModalOverlay) colorModalOverlay.classList.remove('is-open');
      });
    }

    // Обработчик сортировки
    if (sortSelect && sortTrigger && sortPanel) {
      sortTrigger.addEventListener('click', function(e) {
        e.stopPropagation();
        const isOpen = sortPanel.classList.contains('is-open');
        closeAllDropdowns();
        if (!isOpen) {
          sortPanel.classList.add('is-open');
          sortTrigger.classList.add('active');
          sortTrigger.setAttribute('aria-expanded', 'true');
        }
      });
      if (sortOptionsEl) {
        sortOptionsEl.addEventListener('click', function(e) {
          const option = e.target.closest('.sort-option');
          if (!option) return;
          const value = option.getAttribute('data-value') || 'date_new';
          sortSelect.value = value;
          syncSortUi(value);
          closeAllDropdowns();
          currentSort = value;
          void loadCarsPage(1);
        });
      }
      sortSelect.addEventListener('change', () => {
        currentSort = sortSelect.value || 'date_new';
        syncSortUi(currentSort);
        void loadCarsPage(1);
      });
      syncSortUi(sortSelect.value || 'date_new');
    }

    // Тултип для счётчика объявлений
    if (countInfoIcon) {
      const tooltip = document.createElement('div');
      tooltip.className = 'tooltip tooltip--catalog-count';
      tooltip.innerHTML =
        'Число — сколько объявлений проходит наши фильтры: ' +
        'без дубликатов, без электрокаров и без позиций, которые нельзя купить. ' +
        'Поэтому оно может быть меньше, чем на Encar.';
      document.body.appendChild(tooltip);
      function showCountTip() {
        positionTooltip(tooltip, countInfoIcon.getBoundingClientRect());
      }
      function hideCountTip() {
        tooltip.style.display = 'none';
      }
      countInfoIcon.addEventListener('mouseenter', showCountTip);
      countInfoIcon.addEventListener('mouseleave', hideCountTip);
      countInfoIcon.addEventListener('focus', showCountTip);
      countInfoIcon.addEventListener('blur', hideCountTip);
    }

    // Hero: Swiper + Splitting + Anime подгружаются после первого экрана (меньше конкуренции с /api/cars и JSON).
    var heroSwiper = null;
    function loadStylesheetOnce(href) {
      return new Promise(function(res) {
        if (document.querySelector('link[href="' + href + '"]')) { res(); return; }
        var l = document.createElement('link');
        l.rel = 'stylesheet';
        l.href = href;
        l.onload = function() { res(); };
        l.onerror = function() { res(); };
        document.head.appendChild(l);
      });
    }
    function loadScriptOnce(src) {
      return new Promise(function(res) {
        if (document.querySelector('script[src="' + src + '"]')) { res(); return; }
        var s = document.createElement('script');
        s.src = src;
        s.async = true;
        s.onload = function() { res(); };
        s.onerror = function() { res(); };
        document.head.appendChild(s);
      });
    }
    function loadHeroVendorAssets() {
      if (window.__wraHeroLibsP) return window.__wraHeroLibsP;
      window.__wraHeroLibsP = loadStylesheetOnce('https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.css')
        .then(function() { return loadStylesheetOnce('https://unpkg.com/splitting/dist/splitting.css'); })
        .then(function() { return loadScriptOnce('https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.js'); })
        .then(function() { return loadScriptOnce('https://unpkg.com/splitting/dist/splitting.min.js'); })
        .then(function() { return loadScriptOnce('https://cdn.jsdelivr.net/npm/animejs@3.2.2/lib/anime.min.js'); });
      return window.__wraHeroLibsP;
    }
    function initHeroBannerFromLibs() {
      try {
        if (typeof Swiper !== 'undefined' && document.querySelector('.hero-banner-slider')) {
          heroSwiper = new Swiper('.hero-banner-slider', {
            speed: 400,
            loop: true,
            slidesPerView: 1,
            autoplay: { delay: 6000, disableOnInteraction: false },
            pagination: { el: '.hero-banner-pagination', clickable: true },
            spaceBetween: 0,
            observer: true,
            observeParents: true,
          });
        }
      } catch (eHero) {
        console.warn('[catalog] Swiper init skipped', eHero);
      }
      var brandEl = document.querySelector('.hero-banner-brand .brand-name');
      if (brandEl && typeof Splitting !== 'undefined' && typeof anime !== 'undefined') {
        document.fonts.ready.then(function() {
          var result;
          try {
            result = Splitting({ target: brandEl, by: 'lines' })[0];
          } catch (eSp) {
            console.warn('[catalog] Splitting skipped', eSp);
            return;
          }
          if (!result || !result.lines) return;
          var flagEl = brandEl.querySelector('.flag');
          var lines = result.lines;
          var allWords = typeof lines.flat === 'function' ? lines.flat() : [].concat.apply([], lines);
          allWords.forEach(function(el) {
            el.style.opacity = '0';
            el.style.transform = 'translateY(0.6em)';
          });
          if (flagEl) {
            flagEl.style.opacity = '0';
            flagEl.style.transform = 'scale(0.85)';
          }
          anime({
            targets: allWords,
            opacity: 1,
            translateY: 0,
            duration: 650,
            easing: 'easeOutCubic',
            delay: anime.stagger(60, { start: 100 }),
          });
          if (flagEl) {
            anime({
              targets: flagEl,
              opacity: 1,
              scale: 1,
              duration: 500,
              easing: 'easeOutCubic',
              delay: 400,
            });
          }
        });
      }
    }
    function scheduleHeroBannerLibs() {
      var ran = false;
      function run() {
        if (ran) return;
        ran = true;
        loadHeroVendorAssets()
          .then(function() { initHeroBannerFromLibs(); })
          .catch(function() {});
      }
      var heroWrap = document.querySelector('.hero-banner-wrap');
      if (heroWrap && 'IntersectionObserver' in window) {
        var io = new IntersectionObserver(function(entries) {
          if (entries.some(function(en) { return en.isIntersecting; })) {
            try { io.disconnect(); } catch (e1) {}
            run();
          }
        }, { rootMargin: '240px 0px' });
        io.observe(heroWrap);
        setTimeout(function() {
          try { io.disconnect(); } catch (e2) {}
          run();
        }, 5000);
      } else if (window.requestIdleCallback) {
        requestIdleCallback(function() { run(); }, { timeout: 2800 });
      } else {
        setTimeout(run, 400);
      }
    }
    scheduleHeroBannerLibs();

    var _resizeTick = null;
    function _onHeroResize() {
      if (heroSwiper && typeof heroSwiper.update === 'function') {
        heroSwiper.update();
      }
    }
    window.addEventListener('resize', function() {
      if (_resizeTick) clearTimeout(_resizeTick);
      _resizeTick = setTimeout(_onHeroResize, 200);
    });
    setTimeout(_onHeroResize, 900);
  })();