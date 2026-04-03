  (function() {
    const PER_PAGE = 12;
    let page = 1;
    let pageCars = [];
    let catalogTotal = 0;
    let catalogPages = 1;
    let catalogRequestId = 0;
    let useStaticCatalog = false;
    let staticCatalogCache = null;
    const API_BASE = (typeof window.WRA_API_BASE === 'string' ? window.WRA_API_BASE : '').replace(/\/+$/, '');
    function apiUrl(path) {
      return API_BASE + path;
    }
    /**
     * Фолбэк: скачать целиком cars.json в браузер. На проде при ~100k+ машин это гигабайты → OOM и «Aw Snap».
     * По умолчанию разрешён только если API на другом origin (WRA_API_BASE не пустой): тогда локальный cars.json часто маленький снапшот.
     * Чисто статический каталог без API: задайте window.WRA_ALLOW_CATALOG_JSON_FALLBACK = true до catalog.js (и держите выгрузку небольшой или задайте лимит).
     */
    function allowCarsJsonFallback() {
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
    }
    if (filtersOpenBtn && filtersDrawerOverlay) {
      filtersOpenBtn.addEventListener('click', openFiltersDrawer);
      filtersDrawerOverlay.addEventListener('click', closeFiltersDrawer);
    }
    if (filtersDrawerClose) filtersDrawerClose.addEventListener('click', closeFiltersDrawer);

    function closeAllDropdowns() {
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

    function checkboxTemplate(id, filterKey, value, labelHtml) {
      return (
        '<label class="checkbox" data-selected="false">' +
          '<span class="checkbox__input-wrap"><input type="checkbox" id="' + id + '" data-filter="' + filterKey + '" value="' + value + '"></span>' +
          '<span class="checkbox__control"><span class="checkbox__indicator"><svg aria-hidden="true" viewBox="0 0 17 18" fill="none"><polyline points="1 9 7 14 15 4"/></svg></span></span>' +
          '<span class="checkbox__content"><span class="checkbox__label">' + labelHtml + '</span></span>' +
        '</label>'
      );
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
        if (cb.value === value) cb.checked = false;
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
        '페라리': 'Ferrari', '람보르기니': 'Lamborghini', '알파로메오': 'Alfa Romeo', '피아트': 'Fiat'
      },
      bodyType: {
        '세단': 'Sedan', 'SUV': 'SUV', '해치백': 'Hatchback', '왜건': 'Wagon', '쿠페': 'Coupe', '픽업': 'Pickup', '밴': 'Van',
        '중형차': 'Midsize', '대형차': 'Full-size', '소형차': 'Compact', '경차': 'Light car', '미니밴': 'Minivan', 'RV': 'RV',
        '스포츠카': 'Sports car', '승합차': 'Minibus', '화물차': 'Commercial vehicle',
        '크로스오버': 'Crossover', '리무진': 'Limousine', '컨버터블': 'Convertible'
      },
      engineType: {
        '가솔린': 'Gasoline', '디젤': 'Diesel', 'LPG': 'LPG', 'LPG/가솔린': 'LPG/Gasoline', '하이브리드': 'Hybrid',
        '가솔린+전기': 'Hybrid', '전기': 'Electric', '수소': 'Hydrogen', '디젤+전기': 'Diesel Hybrid',
        '바이퓨얼': 'Dual fuel', '친환경': 'Eco', '수소+전기': 'Hydrogen EV', '가솔린+전기+LPG': 'Hybrid LPG'
      },
      transmission: {
        '자동': 'Automatic', '수동': 'Manual', '오토': 'Automatic', '세미자동': 'Semi-Auto', 'CVT': 'CVT', '듀얼 클러치': 'DCT',
        'ISG': 'ISG', '감속기': 'Reducer', '비전동': 'Non-powered'
      },
      color: {
        '검정': 'Black', '검정색': 'Black', '흰색': 'White', '은색': 'Silver', '회색': 'Gray', '빨간색': 'Red',
        '파란색': 'Blue', '남색': 'Navy', '베이지': 'Beige', '갈색': 'Brown', '녹색': 'Green', '노란색': 'Yellow', '주황': 'Orange',
        '골드': 'Gold', '실버': 'Silver', '블랙': 'Black', '화이트': 'White', '레드': 'Red', '블루': 'Blue', '그레이': 'Gray', '그린': 'Green',
        '보라색': 'Purple', '연금색': 'Light gold', '연두색': 'Lime green', '은하색': 'Silver gray', '자주색': 'Purple', '쥐색': 'Dark gray', '진주색': 'Pearl', '청색': 'Blue', '하늘색': 'Sky blue'
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
      '가솔린': 'Бензин', '디젤': 'Дизель', 'LPG': 'Газ', 'LPG/가솔린': 'Газ/бензин', '하이브리드': 'Гибрид', '전기': 'Электро', '가솔린+전기': 'Гибрид', '수소': 'Водород', '디젤+전기': 'Дизель гибрид',
      'Gasoline': 'Бензин', 'Diesel': 'Дизель', 'Electric': 'Электро', 'Hybrid': 'Гибрид', 'Hydrogen': 'Водород', 'LPG/Gasoline': 'Газ/бензин', 'Diesel Hybrid': 'Дизель гибрид',
      '세단': 'Седан', 'SUV': 'Внедорожник', '해치백': 'Хэтчбек', '왜건': 'Универсал', '쿠페': 'Купе', '픽업': 'Пикап', '밴': 'Фургон', '중형차': 'Седан среднего класса', '대형차': 'Седан полноразмерный', '소형차': 'Компакт', '경차': 'Микролитражный', '미니밴': 'Минивэн', 'RV': 'Внедорожник', '스포츠카': 'Спорткар', '승합차': 'Микроавтобус', '화물차': 'Грузовой автомобиль',
      'Sedan': 'Седан', 'Hatchback': 'Хэтчбек', 'Wagon': 'Универсал', 'Coupe': 'Купе', 'Pickup': 'Пикап', 'Van': 'Фургон', 'Midsize': 'Седан среднего класса', 'Full-size': 'Седан полноразмерный', 'Compact': 'Компакт', 'Minivan': 'Минивэн', 'Light car': 'Микролитражный', 'Sports car': 'Спорткар', 'Minibus': 'Микроавтобус', 'Commercial vehicle': 'Грузовой автомобиль',
      'Crossover': 'Кроссовер', 'Convertible': 'Кабриолет', 'Limousine': 'Лимузин', 'Dual fuel': 'Двухтопливный', 'Eco': 'Экологичный', 'Hydrogen EV': 'Водород + электро', 'Hybrid LPG': 'Гибрид LPG', 'ISG': 'ISG', 'Reducer': 'Редуктор', 'Non-powered': 'Без привода',
      '자동': 'Автоматическая', '수동': 'Механическая', '오토': 'Автоматическая', '세미자동': 'Роботизированная', 'CVT': 'Вариатор', '듀얼 클러치': 'Роботизированная',
      'Automatic': 'Автоматическая', 'Manual': 'Механическая', 'Semi-Auto': 'Роботизированная', 'DCT': 'Роботизированная',
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
      let out = '';
      if (ruCategories.indexOf(category) >= 0) {
        const en = toDisplayEn(s, category);
        out = sanitizeUiLabel(toDisplayRu(en || s) || en || s);
      } else {
        let en = toDisplayEn(s, category);
        if (en !== s) {
          out = sanitizeUiLabel(en);
        } else if (['model', 'generation', 'type', 'trim'].indexOf(category) >= 0) {
          const fallback = applyKoreanPhraseFallback(s);
          out = sanitizeUiLabel(fallback || s);
        } else {
          out = sanitizeUiLabel(toDisplayRu(s) || s);
        }
      }
      if (!out && raw) out = raw;
      if (!out && val != null && String(val).length) out = String(val).trim();
      return out || 'Прочее';
    }
    function buildCatalogFilterParams() {
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

      return p;
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
        preserve.add(cb.value);
      });
      const vals = rows.map(function(r) { return r.value; }).filter(Boolean);
      vals.sort(function(a, b) {
        const la = labelCategory ? filterOptionLabel(a, labelCategory) : String(a);
        const lb = labelCategory ? filterOptionLabel(b, labelCategory) : String(b);
        return String(la).localeCompare(String(lb), 'ru');
      });
      renderCheckboxesWithCounts(
        container,
        vals,
        function(v) { return labelCategory ? filterOptionLabel(v, labelCategory) : v; },
        function(v) {
          for (var i = 0; i < rows.length; i++) {
            if (rows[i].value === v) return rows[i].count;
          }
          return 0;
        },
        filterKey
      );
      container.querySelectorAll('input[type=checkbox][data-filter="' + filterKey + '"]').forEach(function(cb) {
        cb.checked = preserve.has(cb.value);
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
        if (r && r.value != null && r.value !== '') countMap[r.value] = r.count;
      });
      const allColors = (colorRows || []).map(function(r) { return r.value; }).filter(Boolean).sort(function(a, b) {
        return (filterOptionLabel(a, 'color') || '').localeCompare(filterOptionLabel(b, 'color') || '', 'ru');
      });

      colorListVisible.innerHTML = '';
      colorModalList.innerHTML = '';
      const restColors = allColors.slice(4);

      function appendColor(container, val, idPrefix) {
        const div = document.createElement('div');
        div.className = 'checkbox-item';
        const id = idPrefix + String(val).replace(/\s/g, '_');
        const labelText = filterOptionLabel(val, 'color');
        const cnt = countMap[val];
        const suffix = cnt != null ? (' <span class="opt-count">(' + Number(cnt).toLocaleString('ru-RU') + ')</span>') : '';
        div.innerHTML = checkboxTemplate(id, 'color', escapeHtml(val), escapeHtml(labelText) + suffix);
        container.appendChild(div);
      }
      allColors.slice(0, 4).forEach(function(val) { appendColor(colorListVisible, val, 'filter-color-'); });
      allColors.forEach(function(val) { appendColor(colorModalList, val, 'filter-color-modal-'); });

      document.querySelectorAll('input[data-filter="color"]').forEach(function(cb) {
        cb.checked = preserve.has(cb.value);
      });
      syncCheckboxVisualStates(colorListVisible);
      syncCheckboxVisualStates(colorModalList);
      syncCheckboxVisualStates(document);
      if (showMoreColorsBtn) showMoreColorsBtn.style.display = restColors.length > 0 ? 'block' : 'none';
    }

    function refreshFacetsFromStaticCache(reqId) {
      if (reqId !== catalogRequestId || !staticCatalogCache || !staticCatalogCache.length) return;
      function dim(omitKeys, pick) {
        var p = paramsForFacet(omitKeys);
        var map = {};
        staticCatalogCache.forEach(function(car) {
          if (!carMatchesParamsUrl(car, p)) return;
          var v = pick(car);
          if (v == null || v === '') return;
          map[v] = (map[v] || 0) + 1;
        });
        return Object.keys(map).map(function(value) { return { value: value, count: map[value] }; });
      }
      function cascade(container, rows, filterKey, labelCat, trigger, allLabel) {
        if (!container) return;
        renderFacetCheckboxList(container, rows || [], filterKey, labelCat);
        if (trigger) setDropdownTriggerText(trigger, container, filterKey, allLabel);
      }
      cascade(markListEl, dim(['marks'], function(c) { return (c.data || c).mark; }), 'mark', 'mark', markTrigger, 'Все марки');
      var selMarks = getSelectedValues(markListEl, 'mark');
      if (selMarks.size === 0) {
        if (modelListEl) modelListEl.innerHTML = '';
        if (generationListEl) generationListEl.innerHTML = '';
        if (trimListEl) trimListEl.innerHTML = '';
        if (modelTrigger) {
          modelTrigger.disabled = true;
          modelTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите марку</span>';
        }
        if (generationTrigger) {
          generationTrigger.disabled = true;
          generationTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите модель</span>';
        }
        if (trimTrigger) {
          trimTrigger.disabled = true;
          trimTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите поколение</span>';
        }
      } else {
        cascade(modelListEl, dim(['models'], function(c) { return (c.data || c).model; }), 'model', 'model', modelTrigger, 'Все модели');
        if (modelTrigger) modelTrigger.disabled = false;
        var selModels = getSelectedValues(modelListEl, 'model');
        if (selModels.size === 0) {
          if (generationListEl) generationListEl.innerHTML = '';
          if (trimListEl) trimListEl.innerHTML = '';
          if (generationTrigger) {
            generationTrigger.disabled = true;
            generationTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите модель</span>';
          }
          if (trimTrigger) {
            trimTrigger.disabled = true;
            trimTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите поколение</span>';
          }
        } else {
          cascade(generationListEl, dim(['generations'], function(c) {
            var d = c.data || c;
            return d.generation || d.configuration || '';
          }), 'generation', 'generation', generationTrigger, 'Все поколения');
          if (generationTrigger) generationTrigger.disabled = false;
          var selGen = getSelectedValues(generationListEl, 'generation');
          if (selGen.size === 0) {
            if (trimListEl) trimListEl.innerHTML = '';
            if (trimTrigger) {
              trimTrigger.disabled = true;
              trimTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите поколение</span>';
            }
          } else {
            cascade(trimListEl, dim(['trims'], function(c) {
              var d = c.data || c;
              return d.gradeName || d.configuration || d.generation || '';
            }), 'trim', 'trim', trimTrigger, 'Все комплектации');
            if (trimTrigger) trimTrigger.disabled = false;
          }
        }
      }
      renderFacetCheckboxList(document.getElementById('bodyList'), dim(['body'], function(c) { return (c.data || c).body_type; }), 'body', 'bodyType');
      renderFacetCheckboxList(document.getElementById('fuelList'), dim(['fuel'], function(c) { return (c.data || c).engine_type; }), 'fuel', 'engineType');
      renderFacetCheckboxList(document.getElementById('transmissionList'), dim(['trans'], function(c) { return (c.data || c).transmission_type; }), 'transmission', 'transmission');
      renderColorFilterFromFacets(dim(['color'], function(c) { return (c.data || c).color; }));
      syncCascadeSlotVisibility();
    }

    async function refreshFacetBars(reqId) {
      if (useStaticCatalog && staticCatalogCache && staticCatalogCache.length) {
        refreshFacetsFromStaticCache(reqId);
        return;
      }
      const params = buildCatalogFilterParams();
      const res = await fetch(apiUrl('/api/facets?' + params.toString()));
      if (!res.ok) throw new Error('facets HTTP ' + res.status);
      const data = await res.json();
      if (reqId !== catalogRequestId) return;

      function cascade(container, rows, filterKey, labelCat, trigger, allLabel) {
        if (!container) return;
        renderFacetCheckboxList(container, rows || [], filterKey, labelCat);
        if (trigger) setDropdownTriggerText(trigger, container, filterKey, allLabel);
      }

      cascade(markListEl, data.marks, 'mark', 'mark', markTrigger, 'Все марки');

      const selMarks = getSelectedValues(markListEl, 'mark');
      if (selMarks.size === 0) {
        if (modelListEl) modelListEl.innerHTML = '';
        if (generationListEl) generationListEl.innerHTML = '';
        if (trimListEl) trimListEl.innerHTML = '';
        if (modelTrigger) {
          modelTrigger.disabled = true;
          modelTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите марку</span>';
        }
        if (generationTrigger) {
          generationTrigger.disabled = true;
          generationTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите модель</span>';
        }
        if (trimTrigger) {
          trimTrigger.disabled = true;
          trimTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите поколение</span>';
        }
      } else {
        cascade(modelListEl, data.models, 'model', 'model', modelTrigger, 'Все модели');
        if (modelTrigger) modelTrigger.disabled = false;

        const selModels = getSelectedValues(modelListEl, 'model');
        if (selModels.size === 0) {
          if (generationListEl) generationListEl.innerHTML = '';
          if (trimListEl) trimListEl.innerHTML = '';
          if (generationTrigger) {
            generationTrigger.disabled = true;
            generationTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите модель</span>';
          }
          if (trimTrigger) {
            trimTrigger.disabled = true;
            trimTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите поколение</span>';
          }
        } else {
          cascade(generationListEl, data.generations, 'generation', 'generation', generationTrigger, 'Все поколения');
          if (generationTrigger) generationTrigger.disabled = false;

          const selGen = getSelectedValues(generationListEl, 'generation');
          if (selGen.size === 0) {
            if (trimListEl) trimListEl.innerHTML = '';
            if (trimTrigger) {
              trimTrigger.disabled = true;
              trimTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите поколение</span>';
            }
          } else {
            cascade(trimListEl, data.trims, 'trim', 'trim', trimTrigger, 'Все комплектации');
            if (trimTrigger) trimTrigger.disabled = false;
          }
        }
      }

      renderFacetCheckboxList(document.getElementById('bodyList'), data.bodies || [], 'body', 'bodyType');
      renderFacetCheckboxList(document.getElementById('fuelList'), data.fuels || [], 'fuel', 'engineType');
      renderFacetCheckboxList(document.getElementById('transmissionList'), data.transmissions || [], 'transmission', 'transmission');
      renderColorFilterFromFacets(data.colors || []);

      syncCascadeSlotVisibility();
    }

    /** Фасеты тяжёлые: не конкурируют с /api/cars за сеть/CPU в первый кадр (как отдельный «filters» у конкурента). */
    function scheduleFacetRefresh(reqId) {
      function run() {
        refreshFacetBars(reqId).catch(function(e) {
          if (reqId === catalogRequestId) console.warn('[catalog] facets failed', e);
        });
      }
      if (typeof requestIdleCallback !== 'undefined') {
        requestIdleCallback(run, { timeout: 2500 });
      } else {
        setTimeout(run, 80);
      }
    }

    let debouncedApplyTimer = null;
    function scheduleDebouncedApplyFilters() {
      if (debouncedApplyTimer) clearTimeout(debouncedApplyTimer);
      debouncedApplyTimer = setTimeout(function() {
        debouncedApplyTimer = null;
        void runApplyFilters();
      }, 320);
    }

    function parseCarsApiPayload(data) {
      var raw = null;
      if (data && Array.isArray(data.result)) raw = data.result;
      else if (data && Array.isArray(data.cars)) raw = data.cars;
      else if (data && Array.isArray(data.items)) raw = data.items;
      var list = Array.isArray(raw) ? raw : [];
      var seenIds = new Set();
      list = list.filter(function(c) {
        var id = c && (c.id != null ? String(c.id) : (c.inner_id != null ? String(c.inner_id) : (c.data && c.data.inner_id != null ? String(c.data.inner_id) : '')));
        if (!id) return true;
        if (seenIds.has(id)) return false;
        seenIds.add(id);
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
        const res = await fetch(apiUrl('/api/cars?' + params.toString()));
        if (!res.ok) throw new Error('cars HTTP ' + res.status);
        const data = await res.json();
        if (reqId !== catalogRequestId) return;
        const parsed = parseCarsApiPayload(data);
        pageCars = parsed.list;
        catalogTotal = parsed.total;
        catalogPages = parsed.pages;
        page = targetPage;
        if (pageCars.length === 0 && catalogTotal > 0 && targetPage > 1) {
          await loadCarsPage(1, reqId);
          return;
        }
        updateFilterCountBadge();
        draw();
      } catch (err) {
        if (reqId !== catalogRequestId) return;
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
              staticCatalogCache = parsedInit.list;
              useStaticCatalog = true;
              loadCarsPageStatic(targetPage, reqId);
              scheduleFacetRefresh(reqId);
              return;
            }
          } catch (e2) { /* fall through */ }
        }
        console.error(err);
        pageCars = [];
        catalogTotal = 0;
        catalogPages = 1;
        if (gridEl) {
          gridEl.setAttribute('aria-busy', 'false');
          gridEl.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; background:var(--wra-surface); border-radius:24px; border:1px solid var(--wra-border);"><p style="margin:0 0 16px;">Не удалось загрузить каталог.</p><a href="index.html" class="btn btn-primary">Обновить страницу</a></div>';
        }
        if (paginationEl) paginationEl.innerHTML = '';
      }
    }

    async function runApplyFilters() {
      const reqId = ++catalogRequestId;
      page = 1;
      try {
        scheduleFacetRefresh(reqId);
        await loadCarsPage(1, reqId);
      } catch (e) {
        if (reqId !== catalogRequestId) return;
        console.error(e);
        if (gridEl) {
          gridEl.setAttribute('aria-busy', 'false');
          gridEl.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; background:var(--wra-surface); border-radius:24px; border:1px solid var(--wra-border);"><p style="margin:0 0 16px;">Не удалось обновить каталог.</p><a href="index.html" class="btn btn-primary">Обновить страницу</a></div>';
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

        // Порядок видов: перед (1), зад (2), левый/правый бок, салон; приоритет — всегда показывать перед в превью
    function getPhotoViewOrder(path, code) {
        const c = String(code || '').toUpperCase().trim();
        if (c === 'FRONT' || c === 'FRONTVIEW' || c === 'PHOTOFRONT' || c === '앞' || c === '정면') return 1;
        if (c === 'REAR' || c === 'BACK' || c === 'REARVIEW' || c === 'PHOTOBACK' || c === 'PHOTOREAR' || c === '뒤' || c === '후면') return 2;
        if (c === 'LEFT' || c === 'PHOTOLEFT' || c === 'LEFTVIEW' || c === '좌') return 3;
        if (c === 'RIGHT' || c === 'PHOTORIGHT' || c === 'RIGHTVIEW' || c === '우') return 4;
        if (c === 'SIDE' || c === 'SIDEVIEW') return 5;
        if (c === 'INTERIOR' || c === 'INNER' || c === 'INSPECTION') return 6;
        const numCode = /^\d+$/.test(c) ? parseInt(c, 10) : null;
        if (numCode !== null) {
            if (numCode === 0 || numCode === 1) return 1;
            if (numCode === 2) return 2;
            if (numCode === 3) return 3;
            if (numCode === 4) return 4;
            return 100 + numCode;
        }
        const p = String(path || '').toLowerCase();
        if (p.includes('photofront') || p.includes('photo_front') || p.includes('front.jpg') || p.includes('frontview') || p.includes('_front_') || p.includes('/front') || p.includes('정면') || p.includes('앞')) return 1;
        if (p.includes('photorear') || p.includes('photo_rear') || p.includes('photoback') || p.includes('photo_back') || p.includes('back.jpg') || p.includes('rearview') || p.includes('_rear_') || p.includes('/rear') || p.includes('/back') || p.includes('후면') || p.includes('뒤')) return 2;
        if (p.includes('photoleft') || p.includes('photo_left') || p.includes('left.jpg') || p.includes('leftview') || p.includes('_left_') || p.includes('(좌)') || p.includes('좌측')) return 3;
        if (p.includes('photoright') || p.includes('photo_right') || p.includes('right.jpg') || p.includes('rightview') || p.includes('_right_') || p.includes('(우)') || p.includes('우측')) return 4;
        if (p.includes('side') || p.includes('бок') || p.includes('profile')) return 5;
        if (p.includes('interior') || p.includes('inner') || p.includes('salon') || p.includes('inside') || p.includes('cabin') || p.includes('inspection')) return 6;
        const numMatch = p.match(/_(\d{2,})\./);
        if (numMatch) return 100 + parseInt(numMatch[1], 10);
        return 50;
    }

    // Выбор картинок только с кузовом (OUTER) с запасным вариантом; порядок как в галерее car.html
    function getPreviewImages(d) {
        let images = [];
        try { images = JSON.parse(d.images || '[]'); } catch { images = []; }

        let hImages = [];
        try { hImages = JSON.parse(d.h_images || '[]'); } catch { hImages = []; }

        if (Array.isArray(images) && images.length && Array.isArray(hImages) && hImages.length) {
            const outerItems = hImages.filter(h => h && h.type === 'OUTER' && h.code);
            const pairs = [];
            outerItems.forEach(h => {
                const code = String(h.code);
                const suffix = `_${code}.`;
                const found = images.find(url => typeof url === 'string' && url.includes(suffix));
                if (found && !pairs.some(p => p.url === found)) {
                    pairs.push({ url: found, code: code });
                }
            });

            if (pairs.length) {
                pairs.sort((a, b) => {
                    const orderA = getPhotoViewOrder(a.url, a.code);
                    const orderB = getPhotoViewOrder(b.url, b.code);
                    if (orderA !== orderB) return orderA - orderB;
                    return String(a.url).localeCompare(b.url);
                });
                let result = pairs.map(p => p.url).slice(0, 4);
                const frontPair = pairs.find(p => getPhotoViewOrder(p.url, p.code) === 1);
                if (frontPair && result[0] !== frontPair.url) {
                    result = result.filter(u => u !== frontPair.url);
                    result.unshift(frontPair.url);
                } else {
                    const firstOrder = result.length ? getPhotoViewOrder(result[0], pairs.find(p => p.url === result[0])?.code) : 0;
                    if (firstOrder === 2) {
                        const notRear = pairs.find(p => getPhotoViewOrder(p.url, p.code) !== 2 && result.includes(p.url));
                        if (notRear && result[0] !== notRear.url) {
                            result = result.filter(u => u !== notRear.url);
                            result.unshift(notRear.url);
                        }
                    }
                }
                return result;
            }
        }

        // Фолбэк: первые 4 фото, сортировка по тому же порядку видов
        if (Array.isArray(images) && images.length) {
            const sorted = images.slice().sort((a, b) => {
                const orderA = getPhotoViewOrder(a, null);
                const orderB = getPhotoViewOrder(b, null);
                if (orderA !== orderB) return orderA - orderB;
                return String(a).localeCompare(b);
            });
            let result = sorted.slice(0, 4);
            const frontUrl = result.find(u => getPhotoViewOrder(u, null) === 1);
            if (frontUrl && result[0] !== frontUrl) {
                result = result.filter(u => u !== frontUrl);
                result.unshift(frontUrl);
            } else if (result.length && getPhotoViewOrder(result[0], null) === 2) {
                const notRear = result.find(u => getPhotoViewOrder(u, null) !== 2);
                if (notRear && result[0] !== notRear) {
                    result = result.filter(u => u !== notRear);
                    result.unshift(notRear);
                }
            }
            return result;
        }
        return [];
    }

    function guessImageType(url) {
        const u = String(url || '').toLowerCase();
        if (u.includes('front') || u.includes('перед') || u.includes('frontview') || u.includes('front_view')) return 'FRONT';
        if (u.includes('rear') || u.includes('зад') || u.includes('back') || u.includes('rearview') || u.includes('rear_view')) return 'REAR';
        if (u.includes('side') || u.includes('бок') || u.includes('profile') || u.includes('sideview') || u.includes('side_view')) return 'SIDE';
        if (u.includes('interior') || u.includes('салон') || u.includes('inside') || u.includes('cabin') || u.includes('interiorview') || u.includes('interior_view')) return 'INTERIOR';
        if (u.includes('wheel') || u.includes('tire') || u.includes('rim') || u.includes('диск')) return 'WHEEL';
        return 'SIDE';
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
        gridEl.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; background:var(--wra-surface); border-radius:24px; border:1px solid var(--wra-border);"><p style="margin:0 0 16px;">Список не загрузился (есть ' + totalN.toLocaleString('ru-RU') + ' объявлений в базе). Обновите страницу.</p><a href="index.html" class="btn btn-primary">Обновить</a></div>';
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
        const detailUrl = car.id != null ? 'car.html?id=' + encodeURIComponent(car.id) : (car.inner_id != null ? 'car.html?id=' + encodeURIComponent(car.inner_id) : (d.inner_id != null ? 'car.html?id=' + encodeURIComponent(d.inner_id) : '#'));

        card.innerHTML = `
          <div class="preview">
            ${isToday ? '<span class="card-badge card-badge-today">Добавлен сегодня</span>' : ''}
            ${images.map(function(img, i) {
              var hero = eagerHeroImage && cardIdx === 0 && i === 0;
              var attrs = hero
                ? 'fetchpriority="high" decoding="async"'
                : 'loading="lazy" decoding="async"';
              return '<img src="' + img + '" alt="" class="' + (i === 0 ? 'active' : '') + '" width="290" height="186" ' + attrs + '>';
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
            window.location.href = 'car.html?id=' + encodeURIComponent(linkId);
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
            var byValue = {};
            document.querySelectorAll('input[data-filter="color"]').forEach(function(cb) {
              byValue[cb.value] = byValue[cb.value] || cb.checked;
            });
            document.querySelectorAll('input[data-filter="color"]').forEach(function(cb) {
              cb.checked = !!byValue[cb.value];
            });
            syncCheckboxVisualStates(document);
            scheduleDebouncedApplyFilters();
            return;
          }
          if (t.id === 'filterPassageCars') {
            scheduleDebouncedApplyFilters();
            return;
          }
          if (t.closest('#bodyList') || t.closest('#fuelList') || t.closest('#transmissionList') || t.closest('.drive-checkbox-wrap')) {
            scheduleDebouncedApplyFilters();
          }
        });
      }

      [[markTrigger, markPanel], [modelTrigger, modelPanel], [generationTrigger, generationPanel], [trimTrigger, trimPanel]].forEach(function(pair) {
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
          }
        });
      });
      document.addEventListener('click', function(e) {
        if (e.target.closest('.filter-dropdown')) return;
        closeAllDropdowns();
      });

      if (markListEl) {
        markListEl.addEventListener('change', function(e) {
          if (!e.target || e.target.getAttribute('data-filter') !== 'mark') return;
          closeAllDropdowns();
          setDropdownTriggerText(markTrigger, markListEl, 'mark', 'Все марки');
          void runApplyFilters();
        });
      }
      if (modelListEl) {
        modelListEl.addEventListener('change', function(e) {
          if (!e.target || e.target.getAttribute('data-filter') !== 'model') return;
          closeAllDropdowns();
          setDropdownTriggerText(modelTrigger, modelListEl, 'model', 'Все модели');
          void runApplyFilters();
        });
      }
      if (generationListEl) {
        generationListEl.addEventListener('change', function(e) {
          if (!e.target || e.target.getAttribute('data-filter') !== 'generation') return;
          closeAllDropdowns();
          setDropdownTriggerText(generationTrigger, generationListEl, 'generation', 'Все поколения');
          void runApplyFilters();
        });
      }
      if (trimListEl) {
        trimListEl.addEventListener('change', function(e) {
          if (!e.target || e.target.getAttribute('data-filter') !== 'trim') return;
          closeAllDropdowns();
          setDropdownTriggerText(trimTrigger, trimListEl, 'trim', 'Все комплектации');
          void runApplyFilters();
        });
      }

      ['powerFrom', 'powerTo', 'engineFrom', 'engineTo', 'priceFrom', 'priceTo', 'mileageFrom', 'mileageTo',
       'insuranceCasesFrom', 'insuranceCasesTo', 'insurancePayoutsFrom', 'insurancePayoutsTo', 'damagedFrom', 'damagedTo'].forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.addEventListener('input', scheduleDebouncedApplyFilters);
      });
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

      if (!markListEl) syncCascadeSlotVisibility();
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
        out.add(cb.value);
      });
      return out;
    }

    function closeFilterDropdownPair(trigger, panel) {
      if (!trigger || !panel) return;
      if (panel.classList.contains('is-open')) {
        panel.classList.remove('is-open');
        trigger.classList.remove('active');
        trigger.setAttribute('aria-expanded', 'false');
      }
    }

    function syncCascadeSlotVisibility() {
      const sm = getSelectedValues(markListEl, 'mark');
      const sMo = getSelectedValues(modelListEl, 'model');
      const sG = getSelectedValues(generationListEl, 'generation');
      const slotModel = document.getElementById('cascadeSlotModel');
      const slotGen = document.getElementById('cascadeSlotGeneration');
      const slotTrim = document.getElementById('cascadeSlotTrim');
      if (slotModel) {
        const show = sm.size > 0;
        if (!show) closeFilterDropdownPair(modelTrigger, modelPanel);
        slotModel.classList.toggle('is-revealed', show);
        slotModel.setAttribute('aria-hidden', show ? 'false' : 'true');
      }
      if (slotGen) {
        const show = sMo.size > 0;
        if (!show) closeFilterDropdownPair(generationTrigger, generationPanel);
        slotGen.classList.toggle('is-revealed', show);
        slotGen.setAttribute('aria-hidden', show ? 'false' : 'true');
      }
      if (slotTrim) {
        const show = sG.size > 0;
        if (!show) closeFilterDropdownPair(trimTrigger, trimPanel);
        slotTrim.classList.toggle('is-revealed', show);
        slotTrim.setAttribute('aria-hidden', show ? 'false' : 'true');
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

    function renderCheckboxesWithCounts(container, values, labelFn, countFn, filterKey) {
      if (!container) return;
      container.innerHTML = '';
      (values || []).forEach(function(val) {
        const div = document.createElement('div');
        div.className = 'checkbox-item';
        const safe = String(val).replace(/\s/g, '_').replace(/[^\w\-]/g, '_');
        const id = 'filter-' + filterKey + '-' + safe;
        const label = labelFn ? labelFn(val) : val;
        const cnt = countFn ? countFn(val) : null;
        const suffix = (cnt != null) ? (' <span class="opt-count">(' + Number(cnt).toLocaleString('ru-RU') + ')</span>') : '';
        div.innerHTML = checkboxTemplate(id, filterKey, escapeHtml(val), escapeHtml(label) + suffix);
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
      if (modelTrigger) { modelTrigger.disabled = true; modelTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите марку</span>'; }
      if (generationTrigger) { generationTrigger.disabled = true; generationTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите модель</span>'; }
      if (trimTrigger) { trimTrigger.disabled = true; trimTrigger.innerHTML = '<span class="trigger-placeholder">Сначала выберите поколение</span>'; }
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
      void runApplyFilters();
    }

    showSkeleton();

    var mappingPromise = (function() {
      try {
        if (typeof AbortController !== 'undefined') {
          var ctrl = new AbortController();
          var to = setTimeout(function() {
            try { ctrl.abort(); } catch (e) {}
          }, 8000);
          return fetch('data/encar_mapping.json', { signal: ctrl.signal })
            .then(function(r) { clearTimeout(to); return r.ok ? r.json() : null; })
            .catch(function() { clearTimeout(to); return null; });
        }
      } catch (e) {}
      return fetch('data/encar_mapping.json')
        .then(function(r) { return r.ok ? r.json() : null; })
        .catch(function() { return null; });
    })();

    mappingPromise.then(function(mapping) {
      if (mapping && typeof mapping === 'object') {
        ['mark', 'model', 'generation', 'type', 'trim'].forEach(function(cat) {
          if (mapping[cat] && typeof mapping[cat] === 'object') {
            filterMappingKoEn[cat] = Object.assign({}, filterMappingKoEn[cat] || {}, mapping[cat]);
          }
        });
      }
    }).catch(function() {});

    (async function bootstrapCatalog() {
      try {
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
        scheduleFacetRefresh(reqId);
        var todayEl = document.getElementById('bannerTodayCount');
        var statsPromise = todayEl
          ? fetch(apiUrl('/api/stats')).then(function(sr) {
              if (!sr.ok) throw new Error('stats HTTP ' + sr.status);
              return sr.json();
            }).catch(function() { return null; })
          : Promise.resolve(null);

        await loadCarsPage(wantPage, reqId);
        if (reqId !== catalogRequestId) return;
        if (wantPage > catalogPages && catalogPages >= 1) {
          var reqClamp = ++catalogRequestId;
          await loadCarsPage(catalogPages, reqClamp);
        }

        if (todayEl) {
          try {
            var st = await statsPromise;
            var n = (st && typeof st.listed_today === 'number') ? st.listed_today : 0;
            todayEl.textContent = n > 0 ? ('+' + n.toLocaleString('ru-RU')) : '+0';
          } catch (e2) {
            todayEl.textContent = '+0';
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
        if (gridEl) {
          gridEl.setAttribute('aria-busy', 'false');
          gridEl.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; background:var(--wra-surface); border-radius:24px; border:1px solid var(--wra-border);"><p style="margin:0 0 16px;">Не удалось загрузить каталог. Проверьте, что API доступен по тому же домену (например /api/cars).</p><a href="index.html" class="btn btn-primary">Обновить страницу</a></div>';
        }
      }
    })();

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

    // Инициализация Swiper баннера — не роняем каталог, если CDN недоступен
    var heroSwiper = null;
    try {
      if (typeof Swiper !== 'undefined') {
        heroSwiper = new Swiper('.hero-banner-slider', {
          speed: 400,
          loop: true,
          slidesPerView: 1,
          autoplay: { delay: 6000, disableOnInteraction: false },
          pagination: {
            el: '.hero-banner-pagination',
            clickable: true,
          },
          spaceBetween: 0,
          observer: true,
          observeParents: true,
        });
      }
    } catch (eHero) {
      console.warn('[catalog] Swiper init skipped', eHero);
    }

    // Анимация .brand-name по строкам (Splitting.js + Anime.js)
    const brandEl = document.querySelector('.hero-banner-brand .brand-name');
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
        const flagEl = brandEl.querySelector('.flag');
        const lines = result.lines;
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
    setTimeout(_onHeroResize, 600);
  })();