    (function() {
        var wraLastCarRawForExport = null;
        var API_BASE = (typeof window.WRA_API_BASE === 'string' ? window.WRA_API_BASE : '').replace(/\/+$/, '');
        function apiUrl(path) {
            return API_BASE + path;
        }

        function allowCarPageJsonFallback() {
            if (typeof window.WRA_ALLOW_CATALOG_JSON_FALLBACK === 'boolean') {
                return window.WRA_ALLOW_CATALOG_JSON_FALLBACK;
            }
            if (window.WRA_CATALOG_API_ONLY === true) return false;
            try {
                var h = (window.location.hostname || '').toLowerCase();
                if (h === 'localhost' || h === '127.0.0.1' || h === '[::1]' || h.endsWith('.local')) return true;
            } catch (e) {}
            return false;
        }

        if (window.WRAAuthFavorites) {
            window.WRAAuthFavorites.initHeader({
                loginButtonSelector: '#headerLoginBtn',
                favoritesButtonSelector: '#headerFavoritesBtn',
                accountButtonSelector: '#headerAccountBtn'
            });
        }
        // ---------- Модалки правой колонки (Подробный расчёт, Как оформить) ----------
        function initOrderModals() {
            var calcOverlay = document.getElementById('calcModalOverlay');
            var calcBody = document.getElementById('calcModalBody');
            var calcTotal = document.getElementById('calcModalTotal');
            var calcTelegram = document.getElementById('calcModalTelegram');
            var howtoOverlay = document.getElementById('howtoModalOverlay');
            if (!calcOverlay || !howtoOverlay) return;

            function openCalcModal() {
                var full = document.getElementById('orderCardCalcFull');
                if (full) {
                    var tpl = full.querySelector('.calc-modal-content-tpl');
                    calcBody.innerHTML = tpl ? tpl.innerHTML : '';
                    calcTotal.textContent = full.getAttribute('data-total') || '—';
                    var formulaEl = document.getElementById('calcModalFormula');
                    if (formulaEl) {
                        var koreaUsd = full.getAttribute('data-korea-usd');
                        var russiaRub = full.getAttribute('data-russia-rub');
                        if (koreaUsd && russiaRub) formulaEl.textContent = 'Расчёт: ' + koreaUsd + ' $ + ' + Number(russiaRub).toLocaleString('ru-RU') + ' ₽';
                        else formulaEl.textContent = '';
                    }
                    if (calcTelegram) calcTelegram.href = typeof TELEGRAM_MANAGER_URL !== 'undefined' ? TELEGRAM_MANAGER_URL : 'https://t.me/nikits15';
                }
                calcOverlay.classList.add('is-open');
                calcOverlay.setAttribute('aria-hidden', 'false');
            }
            function closeCalcModal() {
                calcOverlay.classList.remove('is-open');
                calcOverlay.setAttribute('aria-hidden', 'true');
            }
            function openHowToModal(e) {
                if (e) e.preventDefault();
                howtoOverlay.classList.add('is-open');
                howtoOverlay.setAttribute('aria-hidden', 'false');
            }
            function closeHowToModal() {
                howtoOverlay.classList.remove('is-open');
                howtoOverlay.setAttribute('aria-hidden', 'true');
            }

            document.addEventListener('click', function(e) {
                if (e.target.closest('#openCalcModal')) { openCalcModal(); return; }
                if (e.target.closest('#openHowToModal')) { openHowToModal(e); return; }
                if (e.target.id === 'calcModalClose' || e.target.closest('#calcModalClose')) closeCalcModal();
                if (e.target.id === 'howtoModalClose' || e.target.closest('#howtoModalClose')) closeHowToModal();
                if (e.target === calcOverlay) closeCalcModal();
                if (e.target === howtoOverlay) closeHowToModal();
            });
            document.getElementById('calcModalClose').addEventListener('click', closeCalcModal);
            document.getElementById('howtoModalClose').addEventListener('click', closeHowToModal);
        }
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initOrderModals);
        } else {
            initOrderModals();
        }

        var D = window.WRA_CAR_PAGE_DICTS;
        if (!D) {
            console.error('[car-page] Подключите /js/car-page-dicts.js перед car-page.js');
            return;
        }
        var partNamesRu = D.partNamesRu;
        var statusRu = D.statusRu;
        var filterOptionLabel = D.filterOptionLabel;
        var groupOptionsRu = D.groupOptionsRu;
        var renderOptionsGrouped = D.renderOptionsGrouped;


        // ---------- Общие функции ----------
        function formatKm(km) { return km ? Number(km).toLocaleString() + ' км' : '—'; }
        /** Сумма в вонах → строка в рублях по курсу ЦБ (rubPerWon = руб за 1 вон). */
        function formatWonToRub(won, rubPerWon) {
            if (rubPerWon <= 0) return '—';
            var n = Number(won);
            if (isNaN(n) || n === 0) return '—';
            return Math.round(n * rubPerWon).toLocaleString('ru-RU') + ' ₽';
        }
        /** Пояснение для типа ДТП 1/2/3 (классификация по степени повреждений). */
        var accidentTypeLabels = { '1': 'Лёгкое (мелкие повреждения)', '2': 'Умеренное (средний ремонт)', '3': 'Серьёзное (крупный ремонт)' };

        function renderObjectTable(obj, translate = false) {
            if (!obj || !Object.keys(obj).length) return '';
            let html = `<table class="w-full text-sm data-table">`;
            for (let [k,v] of Object.entries(obj)) {
                if (v && typeof v === 'object') continue;
                if (v != null && v !== '') {
                    const dk = translate ? (partNamesRu[k] || k) : k;
                    const dv = translate ? (statusRu[v] || v) : v;
                    html += `<tr><td class="text-gray-600">${dk}</td><td class="font-medium text-right">${dv}</td></tr>`;
                }
            }
            return html + '</table>';
        }

        function renderBodyPanels(panels) {
            if (!panels?.length) return '';
            let html = '<div class="card"><h2 class="card-title">Диагностика кузова</h2><div class="grid grid-cols-1 md:grid-cols-2 gap-3">';
            panels.forEach(p => {
                const cls = p.status === 'оригинал' ? 'text-green-600' : 'text-amber-600';
                html += `<div class="flex justify-between py-2 border-b border-gray-100"><span class="font-medium">${p.part}</span><span class="${cls}">${p.status}</span></div>`;
            });
            return html + '</div></div>';
        }

        // Зоны схемы кузова (left%, top%, width%, height% — вид сверху: центр капот/багажник, слева и справа боковые панели)
        /* Внешняя схема (вид сверху): координаты в % от изображения details-condition-top */
        var conditionDiagramZones = [
            { part: 'Капот', left: 20, top: 0, width: 60, height: 26 },
            { part: 'Крышка багажника', left: 20, top: 52, width: 60, height: 46 },
            { part: 'Левое переднее крыло', left: 0, top: 0, width: 32, height: 38 },
            { part: 'Левая передняя дверь', left: 0, top: 22, width: 28, height: 38 },
            { part: 'Левая задняя дверь', left: 0, top: 48, width: 28, height: 28 },
            { part: 'Левое заднее крыло', left: 0, top: 74, width: 28, height: 36 },
            { part: 'Правое переднее крыло', left: 80, top: 0, width: 0, height: 38 },
            { part: 'Правая передняя дверь', left: 80, top: 22, width: 8, height: 26 },
            { part: 'Правая задняя дверь', left: 80, top: 48, width: 8, height: 26 },
            { part: 'Правое заднее крыло', left: 80, top: 74, width: 20, height: 36 },
        ];
        var exteriorPanelMap = { 'FRONT_DOOR_LEFT': 'Левая передняя дверь', 'FRONT_DOOR_RIGHT': 'Правая передняя дверь', 'BACK_DOOR_LEFT': 'Левая задняя дверь', 'BACK_DOOR_RIGHT': 'Правая задняя дверь', 'HOOD': 'Капот', 'TRUNK_LID': 'Крышка багажника', 'FRONT_FENDER_LEFT': 'Левое переднее крыло', 'FRONT_FENDER_RIGHT': 'Правое переднее крыло', 'REAR_FENDER_LEFT': 'Левое заднее крыло', 'REAR_FENDER_RIGHT': 'Правое заднее крыло', 'BACK_FENDER_LEFT': 'Левое заднее крыло', 'BACK_FENDER_RIGHT': 'Правое заднее крыло' };
        // Корейские названия деталей (outers) -> русские (для схемы кузова)
        var outerPartKoToRu = {
            '프론트 휀더(좌)': 'Левое переднее крыло',
            '프론트 휀더(우)': 'Правое переднее крыло',
            '후드': 'Капот',
            '트렁크 리드': 'Крышка багажника',
            '프론트 도어(좌)': 'Левая передняя дверь',
            '프론트 도어(우)': 'Правая передняя дверь',
            '리어 도어(좌)': 'Левая задняя дверь',
            '리어 도어(우)': 'Правая задняя дверь',
            '리어 휀더(좌)': 'Левое заднее крыло',
            '리어 휀더(우)': 'Правое заднее крыло'
        };
        // Код/название статуса из inspection.outers -> key и label (как в боте: замена, окрас/сварка, царапина, вмятина, повреждение, коррозия)
        var outerStatusToKey = {
            'X': { key: 'replaced', label: 'Замена' },
            '교환(교체)': { key: 'replaced', label: 'Замена' },
            '교환': { key: 'replaced', label: 'Замена' },
            '교체': { key: 'replaced', label: 'Замена' },
            '부품교체': { key: 'replaced', label: 'Замена' },
            'CHANGE': { key: 'replaced', label: 'Замена' },
            'P': { key: 'painted', label: 'Окрашивание' },
            '도장': { key: 'painted', label: 'Окрашивание' },
            '도색': { key: 'painted', label: 'Окрашивание' },
            'R': { key: 'painted', label: 'Окрашивание' },
            '수리': { key: 'painted', label: 'Окрашивание' },
            '판금': { key: 'painted', label: 'Окрашивание' },
            '리폼': { key: 'painted', label: 'Окрашивание' },
            'METAL': { key: 'painted', label: 'Окрашивание' },
            'DENT': { key: 'unevenness', label: 'Неровности' },
            'SCRATCH': { key: 'scratch', label: 'Царапины' },
            'DAMAGE': { key: 'damage', label: 'Повреждение' },
            'CORROSION': { key: 'corrosion', label: 'Коррозия' }
        };

        /* Внутренняя схема (салон, вид сверху): координаты под изображение details-condition-bottom */
        var interiorZones = [
            { part: 'Водительское сиденье', left: 20, top: 24, width: 18, height: 22 },
            { part: 'Пассажирское сиденье', left: 62, top: 24, width: 18, height: 22 },
            { part: 'Заднее сиденье', left: 32, top: 52, width: 36, height: 28 },
            { part: 'Руль', left: 38, top: 6, width: 24, height: 14 },
            { part: 'Панель приборов', left: 28, top: 0, width: 44, height: 14 },
            { part: 'Потолок', left: 18, top: 84, width: 64, height: 12 },
            { part: 'Центральная консоль', left: 44, top: 16, width: 12, height: 38 },
            { part: 'Передняя дверь (левая) - внутри', left: 2, top: 18, width: 16, height: 52 },
            { part: 'Передняя дверь (правая) - внутри', left: 82, top: 18, width: 16, height: 52 }
        ];
        // Корейские названия внутренних элементов -> русские (расширяемый маппинг)
        var innerPartKoToRu = {
            '운전석 시트': 'Водительское сиденье', '시트(좌)': 'Водительское сиденье', '앞좌석(좌)': 'Водительское сиденье',
            '조수석 시트': 'Пассажирское сиденье', '시트(우)': 'Пассажирское сиденье', '앞좌석(우)': 'Пассажирское сиденье',
            '후석': 'Заднее сиденье', '뒷좌석': 'Заднее сиденье',
            '스티어링 휠': 'Руль', '핸들': 'Руль',
            '대시보드': 'Панель приборов', '계기판': 'Панель приборов',
            '실링': 'Потолок', '천장': 'Потолок',
            '센터페시아': 'Центральная консоль', '콘솔': 'Центральная консоль',
            '내장(좌)': 'Передняя дверь (левая) - внутри', '도어(좌)': 'Передняя дверь (левая) - внутри',
            '내장(우)': 'Передняя дверь (правая) - внутри', '도어(우)': 'Передняя дверь (правая) - внутри'
        };
        var innerStatusToKey = {
            '1': { key: 'good', label: 'Без замечаний' }, '양호': { key: 'good', label: 'Без замечаний' },
            '10': { key: 'damage', label: 'Повреждение' }, '불량': { key: 'damage', label: 'Повреждение' },
            'X': { key: 'replaced', label: 'Замена' }, '교환': { key: 'replaced', label: 'Замена' }, '교체': { key: 'replaced', label: 'Замена' }, 'CHANGE': { key: 'replaced', label: 'Замена' },
            'P': { key: 'painted', label: 'Окрашивание' }, '도장': { key: 'painted', label: 'Окрашивание' }, '도색': { key: 'painted', label: 'Окрашивание' }, 'METAL': { key: 'painted', label: 'Окрашивание' },
            '수리': { key: 'painted', label: 'Окрашивание' }, '판금': { key: 'painted', label: 'Окрашивание' }, '리폼': { key: 'painted', label: 'Окрашивание' },
            'SCRATCH': { key: 'scratch', label: 'Царапины' }, 'DENT': { key: 'unevenness', label: 'Неровности' },
            'DAMAGE': { key: 'damage', label: 'Повреждение' }, 'CORROSION': { key: 'corrosion', label: 'Коррозия' }
        };

        function getIconForStatus(statusKey) {
            var icons = { replaced: '/image/exchange.svg', painted: '/image/painted.svg', scratch: '/image/Scratch.svg', unevenness: '/image/Unevenness.svg', damage: '/image/Damage.svg', corrosion: '/image/Corrosion.svg' };
            return icons[statusKey] || '';
        }

        var interiorPartNames = ['Водительское сиденье', 'Пассажирское сиденье', 'Заднее сиденье', 'Руль', 'Панель приборов', 'Потолок', 'Центральная консоль', 'Передняя дверь (левая) - внутри', 'Передняя дверь (правая) - внутри'];
        function mapToInteriorPart(partKey) {
            var k = (partKey || '').trim();
            if (!k) return '';
            return innerPartKoToRu[k] || (typeof partNamesRu !== 'undefined' && partNamesRu[k]) || k;
        }
        function getInteriorStatus(carData) {
            var status = {};
            var d = (carData && carData.data) || {};
            var extra = d.extra || {};
            var insp = extra.inspection_structured || {};
            var inners = (extra.inspection && extra.inspection.inners) || [];
            var bodyChanged = insp.bodyChanged || {};
            var bodyPanels = insp.bodyPanels || [];
            function norm(s) { return (s || '').trim().replace(/\s+/g, ' '); }
            function setStatus(part, statusKey, label) {
                var key = norm(String(part));
                if (!key) return;
                status[key] = { key: statusKey, label: label };
            }
            inners.forEach(function(item) {
                var children = item.children || [];
                children.forEach(function(ch) {
                    var typeTitle = (ch.type && ch.type.title) ? String(ch.type.title).trim() : '';
                    var partRu = innerPartKoToRu[typeTitle] || typeTitle;
                    if (!partRu) return;
                    var st = ch.statusType || {};
                    var code = (st.code != null) ? String(st.code).trim() : '';
                    var title = (st.title && st.title.trim) ? String(st.title).trim() : '';
                    var statusInfo = innerStatusToKey[code] || innerStatusToKey[title] || { key: 'good', label: 'Без замечаний' };
                    setStatus(partRu, statusInfo.key, statusInfo.label);
                });
            });
            var interior = insp.interior || {};
            if (typeof interior === 'object' && interior !== null) {
                Object.keys(interior).forEach(function(k) {
                    var v = (interior[k] || '').toString().toLowerCase();
                    var partRu = mapToInteriorPart(k);
                    if (!partRu || interiorPartNames.indexOf(partRu) === -1) return;
                    if (v.indexOf('замен') >= 0) setStatus(partRu, 'replaced', 'Замена');
                    else if (v.indexOf('ремонт') >= 0 || v.indexOf('покраск') >= 0 || v.indexOf('불량') >= 0) setStatus(partRu, 'painted', 'Окрашивание');
                    else if (v.indexOf('поврежд') >= 0) setStatus(partRu, 'damage', 'Повреждение');
                    else setStatus(partRu, 'good', 'Без замечаний');
                });
            }
            bodyPanels.forEach(function(p) {
                if (!p.part || interiorPartNames.indexOf(norm(p.part)) === -1) return;
                var s = (p.status || '').toLowerCase();
                if (s === 'замена' || s.indexOf('замен') >= 0) setStatus(p.part, 'replaced', 'Замена');
                else if (s === 'покрашено' || s.indexOf('покраск') >= 0) setStatus(p.part, 'painted', 'Окрашивание');
                else if (s.indexOf('ремонт') >= 0) setStatus(p.part, 'painted', 'Окрашивание');
                else if (s.indexOf('царапин') >= 0) setStatus(p.part, 'scratch', 'Царапины');
                else if (s.indexOf('неровност') >= 0) setStatus(p.part, 'unevenness', 'Неровности');
                else if (s.indexOf('поврежд') >= 0) setStatus(p.part, 'damage', 'Повреждение');
                else if (s.indexOf('коррози') >= 0) setStatus(p.part, 'corrosion', 'Коррозия');
            });
            // «Заменённые/покрашенные детали» — приоритет для схемы (обрабатываем последними)
            Object.keys(bodyChanged).forEach(function(part) {
                var partRu = mapToInteriorPart(part);
                if (!partRu || interiorPartNames.indexOf(partRu) === -1) return;
                var statusStr = (bodyChanged[part] || '').toLowerCase();
                if (statusStr.indexOf('замен') >= 0) setStatus(partRu, 'replaced', 'Замена');
                else if (statusStr.indexOf('покраск') >= 0 || statusStr === 'покрашено') setStatus(partRu, 'painted', 'Окрашивание');
                else if (statusStr.indexOf('ремонт') >= 0) setStatus(partRu, 'painted', 'Окрашивание');
                else if (statusStr.indexOf('царапин') >= 0) setStatus(partRu, 'scratch', 'Царапины');
                else if (statusStr.indexOf('неровност') >= 0) setStatus(partRu, 'unevenness', 'Неровности');
                else if (statusStr.indexOf('поврежд') >= 0) setStatus(partRu, 'damage', 'Повреждение');
                else if (statusStr.indexOf('коррози') >= 0) setStatus(partRu, 'corrosion', 'Коррозия');
                else setStatus(partRu, 'replaced', 'Замена');
            });
            return status;
        }

        function buildExteriorStatus(rawData) {
            var d = (rawData && rawData.data) || {};
            var extra = d.extra || {};
            var insp = extra.inspection_structured || {};
            var bodyChanged = insp.bodyChanged || {};
            var bodyPanels = insp.bodyPanels || [];
            var outers = (extra.inspection && extra.inspection.outers) || [];
            var zoneStatus = {};
            function norm(s) { return (s || '').trim().replace(/\s+/g, ' '); }
            function setStatus(part, statusKey, label) {
                var key = norm(String(part));
                if (!key) return;
                zoneStatus[key] = { key: statusKey, label: label };
            }
            function exteriorPartToZone(part) {
                return (typeof partNamesRu !== 'undefined' && partNamesRu[part]) || outerPartKoToRu[part] || (typeof exteriorPanelMap !== 'undefined' && exteriorPanelMap[part]) || part;
            }
            outers.forEach(function(item) {
                var typeTitle = (item.type && item.type.title) ? String(item.type.title).trim() : '';
                var partRu = outerPartKoToRu[typeTitle] || typeTitle;
                if (!partRu) return;
                var statusTypes = item.statusTypes || [];
                for (var i = 0; i < statusTypes.length; i++) {
                    var st = statusTypes[i];
                    var code = (st && st.code != null) ? String(st.code).trim() : '';
                    var title = (st && st.title) ? String(st.title).trim() : '';
                    var statusInfo = outerStatusToKey[code] || outerStatusToKey[title] || null;
                    if (statusInfo && statusInfo.key !== 'good') {
                        setStatus(partRu, statusInfo.key, statusInfo.label);
                        break;
                    }
                }
                if (!zoneStatus[norm(partRu)] && statusTypes.length) {
                    var first = statusTypes[0];
                    var code0 = first && first.code != null ? String(first.code).trim() : '';
                    var title0 = first && first.title ? String(first.title).trim() : '';
                    var fallback = outerStatusToKey[code0] || outerStatusToKey[title0] || { key: 'replaced', label: 'Замена' };
                    setStatus(partRu, fallback.key, fallback.label);
                }
            });
            bodyPanels.forEach(function(p) {
                if (p.part) {
                    var partRu = exteriorPartToZone(p.part);
                    var s = (p.status || '').toLowerCase();
                    if (s === 'замена') setStatus(partRu, 'replaced', 'Замена');
                    else if (s === 'покрашено') setStatus(partRu, 'painted', 'Окрашивание');
                    else if (s.indexOf('ремонт') >= 0) setStatus(partRu, 'painted', 'Окрашивание');
                    else if (s.indexOf('царапин') >= 0) setStatus(partRu, 'scratch', 'Царапины');
                    else if (s.indexOf('неровност') >= 0) setStatus(partRu, 'unevenness', 'Неровности');
                    else if (s.indexOf('поврежд') >= 0) setStatus(partRu, 'damage', 'Повреждение');
                    else if (s.indexOf('коррози') >= 0) setStatus(partRu, 'corrosion', 'Коррозия');
                }
            });
            // «Заменённые/покрашенные детали» имеют приоритет — обрабатываем последними, перезаписывая схему
            Object.keys(bodyChanged).forEach(function(part) {
                var partRu = exteriorPartToZone(part);
                var status = (bodyChanged[part] || '').toLowerCase();
                if (status.indexOf('замен') >= 0) setStatus(partRu, 'replaced', 'Замена');
                else if (status.indexOf('покраск') >= 0 || status === 'покрашено') setStatus(partRu, 'painted', 'Окрашивание');
                else if (status.indexOf('ремонт') >= 0) setStatus(partRu, 'painted', 'Окрашивание');
                else if (status.indexOf('царапин') >= 0) setStatus(partRu, 'scratch', 'Царапины');
                else if (status.indexOf('неровност') >= 0) setStatus(partRu, 'unevenness', 'Неровности');
                else if (status.indexOf('поврежд') >= 0) setStatus(partRu, 'damage', 'Повреждение');
                else if (status.indexOf('коррози') >= 0) setStatus(partRu, 'corrosion', 'Коррозия');
                else setStatus(partRu, 'replaced', 'Замена');
            });
            return zoneStatus;
        }

        function buildZonesHtml(zones, zoneStatus) {
            function norm(s) { return (s || '').trim().replace(/\s+/g, ' '); }
            return zones.map(function(z) {
                var partNorm = norm(z.part);
                var info = zoneStatus[partNorm] || zoneStatus[z.part];
                var classes = [];
                if (info && info.key !== 'good') classes.push(info.key);
                if (z.top < 30) classes.push('zone-top');
                if (z.left < 20) classes.push('zone-left');
                if (z.left > 80) classes.push('zone-right');
                var cls = classes.join(' ');
                var effectiveKey = (info && info.key !== 'good') ? info.key : '';
                var label = (info && info.key !== 'good') ? info.label : '';
                var iconPath = effectiveKey ? getIconForStatus(effectiveKey) : '';
                var zoneIcon = iconPath ? '<div class="zone-icon-wrap"><img src="' + iconPath + '" alt="" loading="lazy" onerror="this.parentElement.style.display=\'none\'"></div>' : '';
                var tooltipIconTag = iconPath ? '<img src="' + iconPath + '" alt="" class="tooltip-icon" onerror="this.style.display=\'none\'">' : '';
                var tooltipHtml = '<div class="zone-tooltip">' +
                    '<div class="tooltip-body">' +
                    (label ? ('<div class="tooltip-row tooltip-row-title">' + tooltipIconTag + '<span class="tooltip-label">' + label + '</span></div>') : '') +
                    '<div class="tooltip-row tooltip-row-part"><span class="tooltip-part">' + z.part + '</span></div>' +
                    '</div></div>';
                return '<div class="condition-zone ' + cls + '" data-part="' + z.part + '" data-status="' + effectiveKey + '" data-status-text="' + label + '" style="left:' + z.left + '%;top:' + z.top + '%;width:' + z.width + '%;height:' + z.height + '%">' + zoneIcon + tooltipHtml + '</div>';
            }).join('');
        }

        function renderConditionDiagram(rawData, diagnosisPhotos) {
            var exteriorStatus = buildExteriorStatus(rawData);
            var interiorStatus = getInteriorStatus(rawData);
            var exteriorZonesHtml = buildZonesHtml(conditionDiagramZones, exteriorStatus);
            var interiorZonesHtml = buildZonesHtml(interiorZones, interiorStatus);
            var legend = '<div class="condition-legend">' +
                '<span class="legend-item" data-color="replaced"><img src="/image/exchange.svg" alt="" class="legend-icon">Замена</span>' +
                '<span class="legend-item" data-color="painted"><img src="/image/painted.svg" alt="" class="legend-icon">Окрашивание</span>' +
                '<span class="legend-item" data-color="scratch"><img src="/image/Scratch.svg" alt="" class="legend-icon">Царапины</span>' +
                '<span class="legend-item" data-color="unevenness"><img src="/image/Unevenness.svg" alt="" class="legend-icon">Неровности</span>' +
                '<span class="legend-item" data-color="damage"><img src="/image/Damage.svg" alt="" class="legend-icon">Повреждение</span>' +
                '<span class="legend-item" data-color="corrosion"><img src="/image/Corrosion.svg" alt="" class="legend-icon">Коррозия</span>' +
                '</div>';
            var diagPhotos = (diagnosisPhotos || []).filter(function(url) { return typeof url === 'string' && url.trim() !== ''; }).slice(0, 5);
            var photoBlock = '';
            if (diagPhotos.length) {
                photoBlock = '<div id="diagnostics" class="mt-6"><h3 class="text-base font-semibold mb-3 flex items-center">Фото диагностики</h3><div class="grid grid-cols-2 md:grid-cols-4 gap-3 diag-photos-grid">';
                diagPhotos.forEach(function(url, i) {
                    var safeUrl = url.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                    photoBlock += '<div class="diag-photo diag-photo-skeleton rounded-xl overflow-hidden border border-gray-200" data-diag-index="' + i + '" role="button" tabindex="0" style="cursor:pointer;background:var(--wra-gray-200);aspect-ratio:4/3;"><img src="' + safeUrl + '" class="diag-photo-img w-full h-full object-cover" loading="lazy" alt="Фото диагностики ' + (i+1) + '"></div>';
                });
                photoBlock += '</div></div>';
            }
            var diagramTitle = 'Схема состояния кузова';
            var diagramTooltip = 'На схеме отмечены данные, полученные из страховой истории автомобиля и указанные продавцом.<br><br>Для получения точной информации о состоянии автомобиля, необходим его осмотр специалистом Ride Auto';
            return '<div class="card"><h2 class="card-title condition-diagram-title has-tooltip"><span class="ml-0">' + diagramTitle + '</span><span class="tooltip-popup">' + diagramTooltip + '</span></h2>' +
                '<div class="condition-diagrams-row">' +
                '<div class="condition-diagram-item"><p class="condition-diagram-caption">Внешние элементы</p><div class="condition-diagram-wrap"><img src="/image/details-condition-top@1x-HLRtauEL.png" alt="Внешние элементы" loading="lazy" /><div class="condition-overlay">' + exteriorZonesHtml + '</div></div></div>' +
                '<div class="condition-diagram-item"><p class="condition-diagram-caption">Внутренние элементы</p><div class="condition-diagram-wrap"><img src="/image/details-condition-bottom@1x-CVCsf-6Y.png" alt="Внутренние элементы" loading="lazy" /><div class="condition-overlay">' + interiorZonesHtml + '</div></div></div>' +
                '</div>' +
                legend + photoBlock + '</div>';
        }

        function renderComments(c) { return c ? `<div class="card"><h2 class="card-title">Комментарии инспектора</h2><div class="card-body text-muted">${c}</div></div>` : ''; }

        function renderInspectionCombined(insp) {
            if (!insp) return '';
            const hasBasic = insp.basicInfo && Object.values(insp.basicInfo).some(v=>v&&v!=='');
            const hasEngine = insp.engineTransmission && Object.keys(insp.engineTransmission).length > 0;
            const hasChassis = insp.chassis && Object.keys(insp.chassis).length > 0;
            const hasElectrical = insp.electrical && Object.keys(insp.electrical).length > 0;
            if (!hasBasic && !hasEngine && !hasChassis && !hasElectrical) return '';
            const sections = [];
            if (hasBasic) sections.push({ id: 'insp-basic', title: 'Общие данные', content: renderObjectTable(insp.basicInfo, false) });
            if (hasEngine) sections.push({ id: 'insp-engine', title: 'Двигатель и трансмиссия', content: renderObjectTable(insp.engineTransmission, true) });
            if (hasChassis) sections.push({ id: 'insp-chassis', title: 'Ходовая часть', content: renderObjectTable(insp.chassis, true) });
            if (hasElectrical) sections.push({ id: 'insp-electrical', title: 'Электрика', content: renderObjectTable(insp.electrical, true) });
            let html = '<div class="card inspection-block"><h2 class="inspection-block-title">Инспекционная диагностика</h2>';
            html += '<div class="inspection-headers-grid">';
            sections.forEach((s, i) => {
                html += `<button type="button" class="inspection-group-header${i === 0 ? ' is-active' : ''}" data-inspection-index="${i}" aria-expanded="${i === 0}" aria-controls="${s.id}" id="inspection-header-${i}">${s.title}</button>`;
            });
            html += '</div><div class="inspection-panel">';
            sections.forEach((s, i) => {
                html += `<div class="inspection-group-body${i === 0 ? ' is-visible' : ''}" id="${s.id}" role="region" aria-labelledby="inspection-header-${i}">${s.content}</div>`;
            });
            return html + '</div></div>';
        }

        // ---------- Функции для галереи ----------
        /** Номер кадра в пути Encar (/…/id_NNN.jpg) — порядок как на encar.com (коды 001/002 не «углы кузова»). */
        function encarPathSeq(pathOrUrl) {
            var s = String(pathOrUrl || '');
            var m = s.match(/_(\d+)\.(?:jpe?g|png|webp)/i);
            return m ? parseInt(m[1], 10) : 1e9;
        }
        /** Encar: [{path,type}]; иногда JSON-массив строк или объекты с url — приводим к {path,type}. */
        function coerceGalleryItems(rawList) {
            var out = [];
            if (!Array.isArray(rawList)) return out;
            rawList.forEach(function(item) {
                var path = '';
                var typ = 'OUTER';
                if (typeof item === 'string') {
                    path = item.trim();
                } else if (item && typeof item === 'object') {
                    path = String(item.path || item.url || item.image || item.image_url || item.pic_url || '').trim();
                    typ = item.type || 'OUTER';
                }
                if (!path) return;
                if (path.indexOf('//') === 0) path = 'https:' + path;
                out.push({ path: path, type: typ });
            });
            return out;
        }
        function parseDataImagesField(imagesField) {
            if (imagesField == null || imagesField === '') return [];
            var raw = imagesField;
            if (typeof raw === 'string') {
                try { raw = JSON.parse(raw); } catch (e) { return []; }
            }
            if (!Array.isArray(raw)) return [];
            return raw.filter(function(u) { return typeof u === 'string' && u.trim(); }).map(function(u) {
                var p = u.trim();
                if (p.indexOf('//') === 0) p = 'https:' + p;
                return { path: p, type: 'OUTER' };
            });
        }
        function preparePhotos(hImages) {
            const typePriority = { OUTER:1, INNER:2, OPTION:3, THUMBNAIL:4 };
            const items = coerceGalleryItems(hImages);
            const map = new Map();
            items.forEach(function(item) {
                const path = item.path;
                if (!path) return;
                const prio = typePriority[item.type] || 5;
                if (!map.has(path) || prio < map.get(path).priority) map.set(path, { path: path, type: item.type || 'OUTER', priority: prio });
            });
            let list = Array.from(map.values());
            list.sort(function(a, b) {
                if (a.priority !== b.priority) return a.priority - b.priority;
                var sA = encarPathSeq(a.path);
                var sB = encarPathSeq(b.path);
                if (sA !== sB) return sA - sB;
                return String(a.path).localeCompare(b.path);
            });
            return list.map(function(x) { return { path: x.path, type: x.type }; });
        }

        // Глобальные переменные для модалки
        let currentPhotoIndex = 0;
        let photosArray = [];
        var modalPhotosArray = [];

        function getModalThumbUrl(p) {
            var path = p.path || '';
            return path.indexOf('http') === 0 ? path : ('https://ci.encar.com' + path + '?impolicy=heightRate&rh=120&cw=200&ch=120&cg=Center&wtmk=https%3A%2F%2Fci.encar.com%2Fwt_mark%2Fw_mark_04.png&t=20260126173700');
        }
        function getModalMainUrl(p) {
            var path = p.path || '';
            return path.indexOf('http') === 0 ? path : ('https://ci.encar.com' + path + '?impolicy=heightRate&rh=696&cw=1160&ch=696&cg=Center&wtmk=https%3A%2F%2Fci.encar.com%2Fwt_mark%2Fw_mark_04.png&t=20260126173700');
        }

        function prefetchModalMainAt(idx) {
            if (!modalPhotosArray.length) return;
            var i = (idx + modalPhotosArray.length) % modalPhotosArray.length;
            var u = getModalMainUrl(modalPhotosArray[i]);
            if (!u) return;
            var im = new Image();
            im.decoding = 'async';
            im.src = u;
        }

        function openModal(index, sourcePhotos) {
            modalPhotosArray = (sourcePhotos && sourcePhotos.length) ? sourcePhotos : photosArray;
            const modal = document.getElementById('galleryModal');
            if (!modal || !modalPhotosArray.length) return;
            var carContent = document.getElementById('car-content');
            if (carContent) carContent.querySelectorAll('.condition-zone.tooltip-visible').forEach(function(z) { z.classList.remove('tooltip-visible'); });
            currentPhotoIndex = (index + modalPhotosArray.length) % modalPhotosArray.length;

            const modalThumbs = document.getElementById('modalThumbs');
            modalThumbs.dataset.inited = '';
            var thumbsHtml = '';
            modalPhotosArray.forEach(function(p, idx) {
                var tUrl = getModalThumbUrl(p);
                thumbsHtml += '<button type="button" class="modal-thumb' + (idx === currentPhotoIndex ? ' active' : '') + '" data-index="' + idx + '" aria-label="Миниатюра ' + (idx+1) + ' в модалке"><img src="' + tUrl + '" alt="Миниатюра ' + (idx+1) + '"></button>';
            });
            modalThumbs.innerHTML = thumbsHtml;
            modalThumbs.dataset.inited = 'true';

            modalThumbs.onclick = function(e) {
                var btn = e.target.closest('.modal-thumb');
                if (!btn) return;
                var idx = parseInt(btn.dataset.index, 10);
                if (Number.isNaN(idx)) return;
                currentPhotoIndex = idx;
                updateModal();
            };

            updateModal();
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
            modalThumbs.classList.remove('thumb-row-animate');
            requestAnimationFrame(function() { modalThumbs.classList.add('thumb-row-animate'); });
        }

        function updateModal() {
            const modalMain = document.getElementById('modalMain');
            const modalCounter = document.getElementById('modalCounter');
            if (!modalMain || !modalPhotosArray.length) return;
            currentPhotoIndex = (currentPhotoIndex + modalPhotosArray.length) % modalPhotosArray.length;
            var p = modalPhotosArray[currentPhotoIndex];
            var imgUrl = getModalMainUrl(p);
            const wrap = document.getElementById('modalMainImgWrap');
            if (wrap) wrap.innerHTML = '<img src="' + imgUrl + '" alt="Фото автомобиля" decoding="async" fetchpriority="high">';
            modalCounter.textContent = (currentPhotoIndex + 1) + ' / ' + modalPhotosArray.length;
            prefetchModalMainAt(currentPhotoIndex - 1);
            prefetchModalMainAt(currentPhotoIndex + 1);
            prefetchModalMainAt(currentPhotoIndex + 2);

            var thumbs = document.querySelectorAll('.modal-thumb');
            thumbs.forEach(function(thumb, idx) {
                thumb.classList.toggle('active', idx === currentPhotoIndex);
            });
        }

        function closeModal() {
            var m = document.getElementById('galleryModal');
            if (m) m.classList.remove('active');
            document.body.style.overflow = '';
        }

        // Рендер главного блока галереи
        function renderGallery(photos, title) {
            if (!photos.length) return '<div class="card"><p class="card-body text-muted">Нет фотографий</p></div>';
            photosArray = photos; // сохраняем для модалки

            const mainImgUrl = getModalMainUrl(photos[0]);

            return `
                <div class="gallery-section">
                    <div class="gallery-card">
                        <div class="gallery-encar-row">
                            <div class="gallery-main-wrap">
                                <div class="gallery-main" id="galleryMain">
                                    <img src="${mainImgUrl}" alt="${title || 'Фото автомобиля'}" id="mainPhoto" decoding="async" fetchpriority="high">
                                    <button type="button" class="gallery-main-prev" id="galleryMainPrev" aria-label="Предыдущее фото"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M15 19L8 12L15 5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
                                    <button type="button" class="gallery-main-next" id="galleryMainNext" aria-label="Следующее фото"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M9 5L16 12L9 19" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
                                    <div class="gallery-counter-wrap">
                                        <span class="gallery-counter" id="galleryCounter">1/${photos.length}</span>
                                    </div>
                                    <div class="gallery-views">
                                        <i class="fa-regular fa-eye"></i>
                                        <span id="galleryViewsLabel">кол-во просмотров</span>
                                    </div>
                                </div>
                            </div>
                            <div class="gallery-thumbs-col" id="thumbnailsRow">
                                <!-- миниатюры строятся динамически при перелистывании -->
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }

        const TELEGRAM_MANAGER_URL = 'https://t.me/nikits15';
        const TELEGRAM_REG_URL = 'https://telegram.org/';

        // ---------- Рендер правой колонки: компактная карточка заказа + скрытый полный расчёт (для модалки) ----------
        function renderPriceColumn(carData) {
            const d = carData.data || {};
            const manufacturer = filterOptionLabel(d.manufacturerName || d.mark || '', 'mark');
            const model = filterOptionLabel(d.modelName || d.model || '', 'model');
            const grade = filterOptionLabel(d.gradeName || '', 'trim');
            const fullName = [manufacturer, model, grade].filter(Boolean).join(' ').trim() || 'Автомобиль';

            const year = d.year ? d.year.slice(0,4) : '—';
            const km = formatKm(d.km_age);
            const address = d.address || '—';
            const sellerType = d.seller_type || '';

            const priceWon = d.price_won;
            const myPrice = d.my_price;
            const hasEncarPrice = d.price_won != null && Number(d.price_won) > 0;
            const priceUnavailable = !hasEncarPrice || d.price_calc_failed || (myPrice == null || myPrice === '');
            const PRICE_FALLBACK = 'Мало данных для расчёта цены. Обратитесь к менеджеру.';
            const myPriceFormatted = priceUnavailable ? PRICE_FALLBACK : (Math.round(Number(myPrice)).toLocaleString() + ' ₽');

            const priceRub = d.price_rub_estimate;
            const freightRub = d.freight_rub;
            const customsFee = d.customs_fee_rub;
            const duty = d.duty_rub;
            const util = d.util_rub;
            const vatRub = d.vat_rub;
            const customsTotal = d.customs_total_rub;
            const brokerRub = d.broker_rub;
            const commissionRub = d.commission_rub;

            const fmt = function(v) { return (v != null && v !== '') ? Math.round(Number(v)).toLocaleString() + ' ₽' : '—'; };
            const totalForBar = (myPrice && Number(myPrice) > 0) ? Number(myPrice) : 0;
            const carCost = Number(priceRub) || 0;
            const freightOnly = Number(freightRub) || 0;
            const vladRub = Number(brokerRub) || 0;
            const customsRub = Number(customsTotal) || 0;
            const pCar = totalForBar ? Math.round((carCost / totalForBar) * 100) : 25;
            const pKorea = totalForBar ? Math.round((freightOnly / totalForBar) * 100) : 25;
            const pCustoms = totalForBar ? Math.round((customsRub / totalForBar) * 100) : 25;
            const pRussia = totalForBar ? Math.max(0, 100 - pCar - pKorea - pCustoms) : 25;
            const updatedAt = d.offer_created || d.created_at || carData.created_at || '';
            let updatedStr = '—';
            if (updatedAt) {
                const dt = new Date(updatedAt);
                const day = dt.getDate().toString().padStart(2, '0');
                const month = dt.toLocaleString('ru-RU', { month: 'long' });
                const yearNum = dt.getFullYear();
                const h = dt.getHours().toString().padStart(2, '0');
                const m = dt.getMinutes().toString().padStart(2, '0');
                updatedStr = day + ' ' + month + ' ' + yearNum + ' г. в ' + h + ':' + m;
            }
            const showHighBadge = !priceUnavailable && totalForBar > 0 && (Number(customsRub) / totalForBar) > 0.35;
            const showOkBadge = !priceUnavailable && totalForBar > 0 && !showHighBadge;

            const krwPerUsdt = d.krw_per_usdt || 1400;
            const usdtRub = d.usdt_rub || 95;
            const rubPerWon = usdtRub / krwPerUsdt;
            const carUsd = priceWon ? ((priceWon * 10000) + 440000) / krwPerUsdt : 0;
            const koreaExpenseUsd = 1000 + (440000 / krwPerUsdt);
            const koreaTotalUsd = carUsd + 1000;
            const modalCoursesHtml = `
                <div class="calc-modal-courses">
                    <h4>Расчётные курсы:</h4>
                    <div class="calc-modal-courses-pills">
                        <span>1₽ = ${(1 / rubPerWon).toFixed(2)} W</span>
                        <span>1$ = ${Math.round(krwPerUsdt).toLocaleString()} W</span>
                        <span>1$ = ${Math.round(usdtRub)} ₽</span>
                    </div>
                    <details class="calc-modal-why-course">
                        <summary><span class="calc-why-icon" aria-hidden="true"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M7 10l5 5 5-5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></span><span>Почему такой курс?</span></summary>
                        <p>У любой криптовалюты есть курс покупки и курс продажи. Разница между ними — это комиссия обменников, спред и риски ликвидности. При расчёте мы используем реальный курс (KRW→USDT→RUB) с учётом комиссий обменников.</p>
                    </details>
                </div>
            `;
            const modalKoreaHtml = `
                <div class="calc-modal-section">
                    <h4>🇰🇷 Расходы в Корее</h4>
                    <div class="calc-modal-section-row">
                        <span class="key">Стоимость авто на Encar</span>
                        <span class="price">${priceWon ? (carUsd.toFixed(0) + ' $') : '—'}</span>
                    </div>
                    <div class="calc-modal-section-row">
                        <span class="key">Расходы в Южной Корее <span class="info-dot" title="Документы 440k KRW + фрахт 1000$">i</span></span>
                        <span class="price">${(koreaExpenseUsd.toFixed(0))} $</span>
                    </div>
                    <div class="calc-modal-section-row calc-modal-section-total">
                        <span class="key">Итого</span>
                        <span class="price">${priceWon ? (koreaTotalUsd.toFixed(0) + ' $') : '—'}</span>
                    </div>
                </div>
            `;
            const modalRussiaHtml = `
                <div class="calc-modal-section">
                    <h4>🇷🇺 Расходы в РФ</h4>
                    <div class="calc-modal-section-row">
                        <span class="key">Услуги во Владивостоке</span>
                        <span class="price">${fmt(brokerRub)}</span>
                    </div>
                    <p class="calc-modal-section-desc">СБКТС, ЭПТС, лаборатория, перегон, погрузочно-разгрузочные работы, услуги порта, услуги брокера.</p>
                    <div class="calc-modal-section-row">
                        <span class="key">Таможенные расходы <span class="info-dot" title="Сбор, пошлина, утильсбор">i</span></span>
                        <span class="price">${fmt(customsTotal)}</span>
                    </div>
                    <div class="calc-modal-section-sublist">
                        <div class="calc-modal-section-row"><span class="key">Таможенное оформление</span><span class="price">${fmt(customsFee)}</span></div>
                        <div class="calc-modal-section-row"><span class="key">Единая таможенная ставка (ЕТС)</span><span class="price">${fmt(duty)}</span></div>
                        <div class="calc-modal-section-row"><span class="key">Утилизационный сбор</span><span class="price">${fmt(util)}</span></div>
                        <div class="calc-modal-section-row"><span class="key">НДС 20%</span><span class="price">${fmt(vatRub)}</span></div>
                    </div>
                    <div class="calc-modal-section-row">
                        <span class="key">Комиссия нашей компании (10%) <span class="info-dot" title="10% от суммы авто и растаможки">i</span></span>
                        <span class="price">${fmt(commissionRub)}</span>
                    </div>
                    <div class="calc-modal-section-row calc-modal-section-total">
                        <span class="key">Итого</span>
                        <span class="price">${fmt(vladRub + customsRub + (Number(commissionRub) || 0))}</span>
                    </div>
                </div>
            `;

            const metaParts = [year + ' г.', km, address].filter(Boolean);
            if (sellerType) metaParts.push(sellerType);
            const metaHtml = metaParts.length ? metaParts.join(' · ') : '—';
            const originalUrl = (d.url || '').trim() || '#';

            return `
                <div class="order-card" id="orderCard">
                    <div class="order-card-top">
                        <span>Дата обновления ${updatedStr}</span>
                        <div class="order-card-actions">
                            <button type="button" class="order-icon-btn order-icon-copy" aria-label="Копировать" title="Копировать">
                                <img src="/image/copy static.svg" alt="" class="img-static">
                                <img src="/image/copy active.svg" alt="" class="img-active">
                            </button>
                            <a href="${originalUrl}" target="_blank" rel="noopener" class="order-icon-btn order-icon-original" title="Оригинал" aria-label="Оригинал">
                                <img src="/image/link static.svg" alt="" class="img-static">
                                <img src="/image/link active.svg" alt="" class="img-active">
                            </a>
                            <button type="button" class="order-icon-btn order-icon-favourite" aria-label="В избранное">
                                <img src="/image/saved static.svg" alt="" class="img-static">
                                <img src="/image/saved active.svg" alt="" class="img-active">
                            </button>
                        </div>
                    </div>
                    ${showHighBadge ? '<div class="order-badge order-badge-high"><span>Высокая ставка</span><span class="info-icon-wrap" data-tooltip="Высокая доля таможенных расходов. Рекомендуем уточнить итоговую стоимость у менеджера."><img src="/image/Info.svg" alt="" class="info-icon-img" width="14" height="14"></span></div>' : ''}
                    ${showOkBadge ? '<div class="order-badge order-badge-ok"><span>Проходной</span><span class="info-icon-wrap" data-tooltip="Возраст авто от 3 до 5 лет — самая низкая таможенная ставка."><img src="/image/Info.svg" alt="" class="info-icon-img" width="14" height="14"></span></div>' : ''}
                    <div class="order-title-row">
                        <h3 class="order-title">${fullName}</h3>
                    </div>
                    ${metaHtml !== '—' ? `<p class="order-card-meta text-muted">${metaHtml}</p>` : ''}
                    <div class="order-price-block${priceUnavailable ? ' order-price-block--fallback' : ''}">
                        <div class="order-price-main" id="orderPriceMain">${priceUnavailable ? PRICE_FALLBACK : (Math.round(Number(myPrice)).toLocaleString() + ' ₽')}</div>
                        <div class="order-price-sub">под ключ до Владивостока <span class="info-icon-wrap" data-tooltip="Цена под ключ до Владивостока с учётом всех платежей"><img src="/image/Info.svg" alt="" class="info-icon-img" width="14" height="14"></span></div>
                    </div>
                    ${!priceUnavailable && totalForBar ? `
                    <div class="order-breakdown-wrap">
                        <div class="order-breakdown-pills" role="img" aria-label="Доли в стоимости">
                            <span class="pill p1" style="flex:${pCar} 1 0" title="Стоимость авто ${pCar}%"><span class="pill-pct">${pCar}%</span></span>
                            <span class="pill p2" style="flex:${pCustoms} 1 0" title="Таможенные расходы ${pCustoms}%"><span class="pill-pct">${pCustoms}%</span></span>
                            <span class="pill p3" style="flex:${pKorea} 1 0" title="Расходы в Корее ${pKorea}%"><span class="pill-pct">${pKorea}%</span></span>
                            <span class="pill p4" style="flex:${pRussia} 1 0" title="Расходы в РФ ${pRussia}%"><span class="pill-pct">${pRussia}%</span></span>
                        </div>
                    </div>
                    <div class="order-breakdown-legend">
                        <span class="item"><span class="dot d1"></span> Стоимость авто</span>
                        <span class="item"><span class="dot d2"></span> Таможенные расходы</span>
                        <span class="item"><span class="dot d3"></span> Расходы в Корее</span>
                        <span class="item"><span class="dot d4"></span> Расходы в РФ</span>
                    </div>
                    ` : ''}
                    <a href="${TELEGRAM_MANAGER_URL}" target="_blank" rel="noopener" class="order-btn-manager">
                        <i class="fa-regular fa-paper-plane"></i> Написать менеджеру
                    </a>
                    <button type="button" class="order-btn-calc" id="openCalcModal" aria-label="Показать расчёт цены">Показать расчёт цены</button>
                    ${isChannelExportAdminVisible() ? '<button type="button" class="wra-admin-export-btn" id="wraChannelExportBtn" aria-label="Скопировать текст для публикации в канале">Скопировать текст для Telegram</button>' : ''}
                    <div class="order-footer-text">
                        Нет аккаунта в Telegram? <a href="${TELEGRAM_REG_URL}" target="_blank" rel="noopener">Зарегистрироваться</a>
                    </div>
                    <div class="calc-full" id="orderCardCalcFull" data-total="${myPriceFormatted}" data-korea-usd="${priceWon ? koreaTotalUsd.toFixed(0) : ''}" data-russia-rub="${(vladRub + customsRub + (Number(commissionRub) || 0)) || ''}">
                        <div class="calc-modal-content-tpl">${modalCoursesHtml}${modalKoreaHtml}${modalRussiaHtml}</div>
                    </div>
                </div>
                <a href="/buy" class="order-howto-bar"><span>Как купить автомобиль?</span><span class="order-howto-bar-icon" aria-hidden="true"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M10 7l5 5-5 5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></span></a>
            `;
        }

        // ---------- Функция для рендера блока "Похожие по цене" (options.lazy = true — только вернуть HTML, не вставлять) ----------
        async function renderSimilarCars(currentCar, options) {
            const d = currentCar.data || {};
            const currentMark = d.mark || '';
            const currentId = currentCar.id != null ? String(currentCar.id) : (currentCar.inner_id != null ? String(currentCar.inner_id) : (d.inner_id != null ? String(d.inner_id) : ''));

            var similarCars = [];
            try {
                var apiSimJson = null;
                if (window.__wraSimilarCarsPromise) {
                    apiSimJson = await window.__wraSimilarCarsPromise;
                    window.__wraSimilarCarsPromise = null;
                } else if (currentId) {
                    var apiSim = await fetch(apiUrl('/api/similar?car_id=' + encodeURIComponent(currentId) + '&limit=8'));
                    if (apiSim.ok) apiSimJson = await apiSim.json();
                }
                if (apiSimJson && Array.isArray(apiSimJson.result) && apiSimJson.result.length) {
                    similarCars = apiSimJson.result;
                }
            } catch (e) { /* только API, без тяжёлого cars.json */ }

            if (similarCars.length === 0) return '';

            var titleMark = currentMark || ((similarCars[0] && similarCars[0].data) ? similarCars[0].data.mark : '') || '';
            let html = `
                    <div class="similar-cars-section">
                        <div class="similar-cars-header">
                            <h2 class="similar-cars-title">Похожие по цене ${titleMark}</h2>
                        </div>
                        <div class="similar-cars-grid" id="similar-cars-grid">
                `;

            similarCars.forEach(function(car) {
                var cd = car.data || {};
                var images = getPreviewImages(cd);
                var mainImg = images[0] || '';
                var title = [filterOptionLabel(cd.mark, 'mark'), filterOptionLabel(cd.model, 'model'), filterOptionLabel(cd.generation || cd.configuration, 'generation')].filter(Boolean).join(' ').trim();
                if (!title) title = (cd.mark || '') + ' ' + (cd.model || '');
                var model = filterOptionLabel(cd.model, 'model') || cd.model || '';
                var year = cd.year ? String(cd.year).slice(0, 4) : '';
                var km = formatKm(cd.km_age);
                var hasEncarPrice = cd.price_won != null && Number(cd.price_won) > 0;
                var priceUnav = !hasEncarPrice || cd.price_calc_failed || (cd.my_price == null || cd.my_price === '');
                var price = priceUnav ? 'Мало данных для расчёта цены' : (Math.round(Number(cd.my_price)).toLocaleString() + ' ₽');
                var linkId = car.id != null ? car.id : (car.inner_id != null ? car.inner_id : (cd.inner_id != null ? cd.inner_id : ''));

                html += `
                        <div class="similar-car-card">
                            <a href="/detail/${encodeURIComponent(linkId)}" class="similar-car-link">
                                <div class="similar-car-image">
                                    <img src="${mainImg}" alt="${title}" loading="lazy" decoding="async">
                                </div>
                                <div class="similar-car-info">
                                    <h3 class="similar-car-title">${title}</h3>
                                    <div class="similar-car-model">${model}</div>
                                    <div class="similar-car-details">
                                        <div class="similar-car-mileage">${year} • ${km}</div>
                                        <div class="similar-car-price">${price}</div>
                                    </div>
                                </div>
                            </a>
                        </div>
                    `;
            });

            html += `
                        </div>
                    </div>
                `;

            if (!options || !options.lazy) {
                const container = document.getElementById('car-content');
                if (container) {
                    container.insertAdjacentHTML('beforeend', html);
                }
            }
            return html;
        }

        function setupSimilarCarsImageSkeleton(scope) {
            const root = scope || document;
            root.querySelectorAll('.similar-car-image').forEach(function(wrap) {
                var img = wrap.querySelector('img');
                if (!img) return;
                function show() { wrap.classList.add('similar-loaded'); }
                if (img.complete && img.naturalWidth > 0) {
                    show();
                    return;
                }
                img.addEventListener('load', show, { once: true });
                img.addEventListener('error', show, { once: true });
            });
        }

        // ---------- Превью в «Похожие» — порядок кадров по номеру в URL Encar (см. catalog.js) ----------
        function getPreviewImages(d) {
            var images = [];
            try { images = JSON.parse(d.images || '[]'); } catch (e) { images = []; }
            if (!Array.isArray(images) || !images.length) return [];
            var base = (typeof window !== 'undefined' && window.location && window.location.href) ? window.location.href : 'https://rideauto.ru/';
            var urls = images.filter(function(u) { return typeof u === 'string' && u.trim(); });
            function seqFrom(u) {
                try {
                    var x = new URL(String(u).trim(), base);
                    var m = (x.pathname || '').match(/_(\d+)\.(?:jpe?g|png|webp)$/i);
                    if (m) return parseInt(m[1], 10);
                } catch (e2) {}
                var m2 = String(u || '').match(/_(\d+)\.(?:jpe?g|png|webp)/i);
                return m2 ? parseInt(m2[1], 10) : 1e9;
            }
            function pen(u) {
                var s = String(u || '').toLowerCase();
                if (s.includes('wheel') || s.includes('tire') || s.includes('rim') || s.includes('диск')) return 1;
                if (s.includes('타이어') || s.includes('휠')) return 1;
                return 0;
            }
            var scored = urls.map(function(u) { return { u: u, seq: seqFrom(u), p: pen(u) }; });
            scored.sort(function(a, b) {
                if (a.p !== b.p) return a.p - b.p;
                if (a.seq !== b.seq) return a.seq - b.seq;
                return a.u.localeCompare(b.u);
            });
            return scored.slice(0, 4).map(function(x) { return x.u; });
        }

        var motorHpByCodeCar = {};
        function normalizeMotorCodeCar(s) {
            return String(s || '').replace(/\s+/g, '').toUpperCase();
        }
        function extractInspectionMotorCodeCar(d) {
            try {
                var det = d && d.extra && d.extra.inspection && d.extra.inspection.master && d.extra.inspection.master.detail;
                return (det && (det.motorType || det.motor_type || det.engineCode)) || '';
            } catch (e) { return ''; }
        }
        function buildMotorHpIndexCar(em) {
            motorHpByCodeCar = {};
            if (!em || typeof em !== 'object') return;
            var list = Array.isArray(em) ? em : (Array.isArray(em.engines) ? em.engines : []);
            list.forEach(function(row) {
                if (!row || typeof row !== 'object') return;
                var codes = row.motor_codes || row.motorCodes;
                if (!Array.isArray(codes)) return;
                var hp = parseInt(String(row.hp || '').replace(/\D/g, ''), 10);
                if (isNaN(hp) || hp < 20 || hp > 2000) return;
                var pr = parseInt(row.priority, 10) || 0;
                codes.forEach(function(c) {
                    var key = normalizeMotorCodeCar(c);
                    if (!key) return;
                    var prev = motorHpByCodeCar[key];
                    if (!prev || pr >= prev.priority) motorHpByCodeCar[key] = { hp: hp, priority: pr };
                });
            });
            Object.keys(motorHpByCodeCar).forEach(function(k) {
                motorHpByCodeCar[k] = motorHpByCodeCar[k].hp;
            });
        }
        function getPowerDisplayForSpecs(d) {
            var v = d.power || d.hp || d.outputHorsepower || d.power_hp;
            if (v) {
                var n = parseInt(String(v).replace(/\D/g, ''), 10);
                if (!isNaN(n) && n >= 20 && n <= 2000) {
                    var est0 = d.power_estimated === true || d.power_source === 'engine_map' || d.power_source === 'power_lookup';
                    return (est0 ? '≈' : '') + n + ' л.с.';
                }
            }
            var mc = normalizeMotorCodeCar(extractInspectionMotorCodeCar(d));
            if (mc && motorHpByCodeCar[mc] != null) {
                var nh = motorHpByCodeCar[mc];
                if (nh >= 20 && nh <= 2000) return '≈' + nh + ' л.с.';
            }
            return '';
        }

        function formatDisplacementLitersExport(d) {
            var v = d.displacement || d.engine_volume || d.engineDisplacement || '';
            if (v == null || v === '') return '';
            var num = parseInt(String(v).trim().replace(/\s/g, '').replace(/[^\d]/g, ''), 10);
            if (isNaN(num) || num <= 0) return '';
            var L = num / 1000;
            return L.toFixed(1).replace(',', '.') + ' л';
        }
        function formatYearMonthExport(y) {
            var digits = String(y == null ? '' : y).replace(/[^\d]/g, '');
            if (digits.length >= 6) return digits.slice(0, 4) + '.' + digits.slice(4, 6);
            if (digits.length >= 4) return digits.slice(0, 4);
            return '';
        }
        function parseHpFromPowerDisplay(s) {
            var m = String(s || '').replace(/≈/g, '').match(/(\d{2,4})\s*л\.с\./i);
            return m ? parseInt(m[1], 10) : NaN;
        }
        function getTorqueNmExport(d) {
            var t = d.torque_nm || d.torqueNm || d.torque;
            if (t != null && t !== '') {
                var n = parseInt(String(t).replace(/\D/g, ''), 10);
                if (!isNaN(n) && n > 0 && n < 2000) return n;
            }
            try {
                var det = d.extra && d.extra.inspection && d.extra.inspection.master && d.extra.inspection.master.detail;
                if (det && det.maxTorque != null) {
                    var n2 = parseInt(String(det.maxTorque).replace(/\D/g, ''), 10);
                    if (!isNaN(n2) && n2 > 0) return n2;
                }
            } catch (e) {}
            return null;
        }
        function buildReportExportUrl(raw) {
            var base = typeof window.WRA_CHANNEL_EXPORT_REPORT_BASE === 'string' ? window.WRA_CHANNEL_EXPORT_REPORT_BASE.trim() : '';
            var id = '';
            if (typeof window.WRA_CHANNEL_EXPORT_REPORT_SLUG === 'function') {
                try { id = String(window.WRA_CHANNEL_EXPORT_REPORT_SLUG(raw) || '').trim(); } catch (e) {}
            }
            if (!id) {
                id = raw.id != null ? String(raw.id) : (raw.inner_id != null ? String(raw.inner_id) : '');
                var dd = raw.data || {};
                if (!id && dd.inner_id != null) id = String(dd.inner_id);
            }
            if (!id) return '';
            if (base) return base.replace(/\/?$/, '/') + id;
            try {
                if (typeof window.wraCarDetailUrl === 'function') return window.wraCarDetailUrl(id);
                return new URL('/detail/' + encodeURIComponent(id), window.location.href).href;
            } catch (e2) { return ''; }
        }
        function buildChannelExportText(raw) {
            var d = raw.data || {};
            var lines = [];
            var mark = filterOptionLabel(d.manufacturerName || d.mark || '', 'mark');
            var model = filterOptionLabel(d.modelName || d.model || '', 'model');
            var gen = filterOptionLabel(d.generation || '', 'generation');
            var modelSeg = gen ? (model + ' (' + gen + ')') : model;
            var grade = filterOptionLabel(d.gradeName || d.configuration || '', 'trim');
            var titleParts = [mark, modelSeg, grade].filter(Boolean);
            lines.push('🏎' + titleParts.join(' '));

            var dispL = formatDisplacementLitersExport(d);
            var engType = filterOptionLabel(d.engine_type, 'engineType');
            var engLine = '';
            if (dispL && engType) engLine = dispL + ', ' + engType;
            else if (dispL) engLine = dispL;
            else if (engType) engLine = engType;
            if (engLine) lines.push('• Двигатель: ' + engLine);

            var powStr = getPowerDisplayForSpecs(d);
            if (powStr) {
                var powDisplay = String(powStr).replace(/^≈\s*/, '');
                var hp = parseHpFromPowerDisplay(powStr);
                if (!isNaN(hp)) {
                    var kw = Math.round(hp * 0.735499);
                    lines.push('• Мощность: ' + powDisplay + ' (' + kw + ' кВт)');
                } else {
                    lines.push('• Мощность: ' + powDisplay);
                }
            }
            var tq = getTorqueNmExport(d);
            if (tq != null) lines.push('• Крутящий момент: ' + tq + ' Н·м');

            var driveVal = filterOptionLabel(d.drive_type || d.prep_drive_type, 'type');
            if (driveVal) lines.push('• Привод: ' + driveVal);

            var trans = filterOptionLabel(d.transmission_type, 'transmission');
            if (trans) lines.push('• Трансмиссия: ' + trans);

            var ym = formatYearMonthExport(d.year || d.yearMonth);
            if (ym) lines.push('• Дата выпуска: ' + ym);

            if (d.km_age != null && d.km_age !== '') {
                lines.push('• Пробег: ' + Number(d.km_age).toLocaleString('ru-RU') + ' км');
            }

            lines.push('');

            var trimName = filterOptionLabel(d.configuration || d.gradeName, 'trim') || 'стандартная';
            lines.push('Комплектация ' + trimName + ':');
            lines.push('');

            var codes = (d.options && d.options.standard) || [];
            if (codes.length) {
                var groups = groupOptionsRu(codes);
                var orderedCategories = ['Экстерьер и салон', 'Безопасность', 'Комфорт и мультимедиа', 'Сиденья', 'Другое'];
                orderedCategories.forEach(function(cat) {
                    if (groups[cat] && groups[cat].length) {
                        groups[cat].forEach(function(opt) {
                            lines.push('> ' + opt);
                        });
                    }
                });
            }

            lines.push('');

            var reportUrl = buildReportExportUrl(raw);
            if (reportUrl) {
                lines.push('Посмотреть отчёт об истории авто (' + reportUrl + ')');
                lines.push('');
            }

            var myPrice = d.my_price;
            var hasEncarPrice = d.price_won != null && Number(d.price_won) > 0;
            var priceUnavailable = !hasEncarPrice || d.price_calc_failed || (myPrice == null || myPrice === '');
            if (!priceUnavailable) {
                lines.push('💳 Цена во Владивостоке под ключ:  ' + Math.round(Number(myPrice)).toLocaleString('ru-RU') + ' руб.');
            } else {
                lines.push('💳 Цена во Владивостоке под ключ:  уточняйте у менеджера');
            }

            var pub = new Date();
            var dd = String(pub.getDate()).padStart(2, '0');
            var mm = String(pub.getMonth() + 1).padStart(2, '0');
            var yyyy = pub.getFullYear();
            lines.push('');
            lines.push('Цена является актуальной на момент публикации — ' + dd + '.' + mm + '.' + yyyy);

            return lines.join('\n');
        }

        function isChannelExportAdminVisible() {
            return !!(window.WRAAuthFavorites && typeof window.WRAAuthFavorites.isChannelExportAdmin === 'function' && window.WRAAuthFavorites.isChannelExportAdmin());
        }

        function bindWraChannelExportButton(rawData) {
            var exportBtn = document.getElementById('wraChannelExportBtn');
            if (!exportBtn || !rawData) return;
            var exportBtnDefault = 'Скопировать текст для Telegram';
            exportBtn.textContent = exportBtnDefault;
            exportBtn.onclick = function() {
                var text = buildChannelExportText(rawData);
                function fallbackCopy(t) {
                    var ta = document.createElement('textarea');
                    ta.value = t;
                    ta.setAttribute('readonly', '');
                    ta.style.position = 'fixed';
                    ta.style.left = '-9999px';
                    document.body.appendChild(ta);
                    ta.select();
                    try { document.execCommand('copy'); } catch (e) {}
                    document.body.removeChild(ta);
                }
                function doneOk() {
                    exportBtn.textContent = 'Скопировано в буфер';
                    setTimeout(function() { exportBtn.textContent = exportBtnDefault; }, 2200);
                }
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(text).then(doneOk).catch(function() {
                        fallbackCopy(text);
                        doneOk();
                    });
                } else {
                    fallbackCopy(text);
                    doneOk();
                }
            };
        }

        function syncWraChannelExportButton() {
            if (!wraLastCarRawForExport) return;
            var calc = document.getElementById('openCalcModal');
            if (!calc || !calc.parentNode) return;
            var existing = document.getElementById('wraChannelExportBtn');
            var should = isChannelExportAdminVisible();
            if (should && !existing) {
                var btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'wra-admin-export-btn';
                btn.id = 'wraChannelExportBtn';
                btn.setAttribute('aria-label', 'Скопировать текст для публикации в канале');
                btn.textContent = 'Скопировать текст для Telegram';
                calc.parentNode.insertBefore(btn, calc.nextSibling);
                bindWraChannelExportButton(wraLastCarRawForExport);
            } else if (!should && existing) {
                existing.remove();
            } else if (should && existing) {
                bindWraChannelExportButton(wraLastCarRawForExport);
            }
        }

        document.addEventListener('wra-auth-changed', syncWraChannelExportButton);

        // ---------- Главная функция отрисовки ----------
        function renderCar(rawData) {
            const container = document.getElementById('car-content');
            if (!container) return;
            wraLastCarRawForExport = rawData;

            const d = rawData.data || {};
            var breadcrumbId = document.getElementById('breadcrumb-id');
            var breadcrumbTitle = document.getElementById('breadcrumb-title');
            if (breadcrumbId) breadcrumbId.textContent = 'ID ' + (rawData.id || rawData.inner_id || '—');
            if (breadcrumbTitle) breadcrumbTitle.textContent = [filterOptionLabel(d.mark, 'mark'), filterOptionLabel(d.model, 'model'), d.generation ? filterOptionLabel(d.generation, 'generation') : ''].filter(Boolean).join(' ');
            const extra = d.extra || {};
            let insp = extra.inspection_structured || {};
            // Fallback 1: из extra.diagnosis.items (внешние панели)
            if ((!insp.bodyPanels || !insp.bodyPanels.length) && (!insp.bodyChanged || !Object.keys(insp.bodyChanged).length) && extra.diagnosis && extra.diagnosis.items && extra.diagnosis.items.length) {
                const panelMap = {
                    'FRONT_DOOR_LEFT': 'Левая передняя дверь', 'FRONT_DOOR_RIGHT': 'Правая передняя дверь',
                    'BACK_DOOR_LEFT': 'Левая задняя дверь', 'BACK_DOOR_RIGHT': 'Правая задняя дверь',
                    'HOOD': 'Капот', 'TRUNK_LID': 'Крышка багажника',
                    'FRONT_FENDER_LEFT': 'Левое переднее крыло', 'FRONT_FENDER_RIGHT': 'Правое переднее крыло',
                    'REAR_FENDER_LEFT': 'Левое заднее крыло', 'REAR_FENDER_RIGHT': 'Правое заднее крыло',
                    'BACK_FENDER_LEFT': 'Левое заднее крыло', 'BACK_FENDER_RIGHT': 'Правое заднее крыло'
                };
                const statusMap = { 'NORMAL': 'оригинал', 'REPLACEMENT': 'замена' };
                const bodyPanels = [];
                const bodyChanged = {};
                extra.diagnosis.items.forEach(function(item) {
                    const name = item.name;
                    const part = panelMap[name];
                    if (!part) return;
                    const code = item.resultCode || item.resultCodeType;
                    const raw = (item.result || '').trim();
                    let status = code ? (statusMap[code] || code) : (raw === '정상' || raw === '원장' ? 'оригинал' : raw === '교체' ? 'замена' : raw || 'оригинал');
                    bodyPanels.push({ part: part, status: status });
                    if (status === 'замена') bodyChanged[part] = 'замена';
                });
                insp = Object.assign({}, insp, { bodyPanels: bodyPanels, bodyChanged: bodyChanged });
            }
            // Fallback 2: из extra.inspection.outers (внешние и внутренние детали, если inspection_structured пустой)
            if ((!insp.bodyChanged || !Object.keys(insp.bodyChanged).length) && extra.inspection && extra.inspection.outers && extra.inspection.outers.length) {
                var outerRu = { '프론트 휀더(좌)': 'Левое переднее крыло', '프론트 휀더(우)': 'Правое переднее крыло', '후드': 'Капот', '트렁크 리드': 'Крышка багажника', '프론트 도어(좌)': 'Левая передняя дверь', '프론트 도어(우)': 'Правая передняя дверь', '리어 도어(좌)': 'Левая задняя дверь', '리어 도어(우)': 'Правая задняя дверь', '리어 휀더(좌)': 'Левое заднее крыло', '리어 휀더(우)': 'Правое заднее крыло', '프론트 펜더 왼쪽': 'Левое переднее крыло', '프론트 펜더 오른쪽': 'Правое переднее крыло', '리어 펜더 왼쪽': 'Левое заднее крыло', '리어 펜더 오른쪽': 'Правое заднее крыло', '프론트 도어 왼쪽': 'Левая передняя дверь', '프론트 도어 오른쪽': 'Правая передняя дверь', '리어 도어 왼쪽': 'Левая задняя дверь', '리어 도어 오른쪽': 'Правая задняя дверь' };
                var innerRu = { '운전석 시트': 'Водительское сиденье', '시트(좌)': 'Водительское сиденье', '앞좌석(좌)': 'Водительское сиденье', '조수석 시트': 'Пассажирское сиденье', '시트(우)': 'Пассажирское сиденье', '앞좌석(우)': 'Пассажирское сиденье', '후석': 'Заднее сиденье', '뒷좌석': 'Заднее сиденье', '스티어링 휠': 'Руль', '핸들': 'Руль', '대시보드': 'Панель приборов', '계기판': 'Панель приборов', '실링': 'Потолок', '천장': 'Потолок', '센터페시아': 'Центральная консоль', '콘솔': 'Центральная консоль', '내장(좌)': 'Передняя дверь (левая) - внутри', '도어(좌)': 'Передняя дверь (левая) - внутри', '내장(우)': 'Передняя дверь (правая) - внутри', '도어(우)': 'Передняя дверь (правая) - внутри', '시트': 'Водительское сиденье', '도어트림': 'Передняя дверь (левая) - внутри' };
                var statusRuMap = { '교체': 'замена', '도장': 'покрашено', '판금': 'ремонт', '수리': 'ремонт', '교환': 'замена', '도색': 'покрашено', '리폼': 'ремонт', '부품교체': 'замена', '정상': 'оригинал' };
                var bodyChangedFromOuters = {};
                var interiorFromOuters = {};
                extra.inspection.outers.forEach(function(part) {
                    var typeObj = part.type || part;
                    var partName = (typeObj.title || typeObj.partName || part.partName || part.name || part.part || part.title || '').toString().trim();
                    if (!partName) return;
                    var statusType = part.statusType || part.statusTypes && part.statusTypes[0] || {};
                    var status = (statusType.title || statusType.name || part.status || part.result || '').toString().trim();
                    var statusLower = (status || '').toLowerCase();
                    var statusRaw = status || '';
                    var isReplacement = (statusLower.indexOf('замен') >= 0 || statusLower.indexOf('покраш') >= 0 || statusLower.indexOf('painted') >= 0 || statusLower.indexOf('replaced') >= 0) || (/교체|도장|판금|수리|교환|도색|리폼|부품교체/.test(statusRaw));
                    var partRu = outerRu[partName] || partName;
                    var statusRuVal = statusRuMap[status] || status;
                    if (isReplacement) bodyChangedFromOuters[partRu] = statusRuVal;
                    var low = partName.toLowerCase();
                    if (/시트|내장|트림|interior|салон|seat|сиденье/.test(partName) || /interior|салон|seat|сиденье/.test(low)) {
                        interiorFromOuters[partName] = status;
                        var partInteriorRu = innerRu[partName] || partName;
                        if (isReplacement && partInteriorRu !== partName) bodyChangedFromOuters[partInteriorRu] = statusRuVal;
                    }
                });
                insp = Object.assign({}, insp, { bodyChanged: Object.assign({}, insp.bodyChanged || {}, bodyChangedFromOuters), interior: Object.assign({}, insp.interior || {}, interiorFromOuters) });
            }
            if (!d.extra) d.extra = {};
            d.extra.inspection_structured = insp;

            // Фото: h_images (Encar) + data.images (Dongchedi и др.) — объединяем и убираем дубликаты по URL.
            let hImagesRaw = [];
            try { hImagesRaw = JSON.parse(d.h_images || '[]'); } catch (e0) { hImagesRaw = []; }
            var galleryItems = coerceGalleryItems(hImagesRaw);
            var fromDataImages = parseDataImagesField(d.images);
            var seenGallery = Object.create(null);
            galleryItems.forEach(function(p) { if (p.path) seenGallery[p.path] = true; });
            fromDataImages.forEach(function(p) {
                if (p.path && !seenGallery[p.path]) {
                    seenGallery[p.path] = true;
                    galleryItems.push(p);
                }
            });
            const sortedPhotos = preparePhotos(galleryItems).filter(p => p.type !== 'THUMBNAIL');

            // Левая колонка (основная информация) – без верхнего блока titleHtml
            const manufacturerName = filterOptionLabel(d.manufacturerName || d.mark || '', 'mark');
            const modelName = filterOptionLabel(d.modelName || d.model || '', 'model');
            const gradeName = filterOptionLabel(d.gradeName || '', 'trim');
            const fullNameForGallery = [manufacturerName, modelName, gradeName].filter(Boolean).join(' ').trim() || 'Автомобиль';

            const galleryHtml = renderGallery(sortedPhotos, fullNameForGallery);

            var driveVal = filterOptionLabel(d.drive_type || d.prep_drive_type, 'type') || '';
            var powerVal = getPowerDisplayForSpecs(d);
            const specs = [
                { label: 'Марка', value: filterOptionLabel(d.mark, 'mark') },
                { label: 'Модель', value: filterOptionLabel(d.model, 'model') },
                { label: 'Поколение', value: filterOptionLabel(d.generation, 'generation') },
                { label: 'Комплектация', value: filterOptionLabel(d.configuration || d.gradeName, 'trim') },
                { label: 'Год выпуска', value: d.year?.slice(0,4) },
                { label: 'Цвет', value: filterOptionLabel(d.color, 'color') },
                { label: 'Пробег', value: formatKm(d.km_age) },
                { label: 'Тип двигателя', value: filterOptionLabel(d.engine_type, 'engineType') },
                { label: 'Коробка', value: filterOptionLabel(d.transmission_type, 'transmission') },
                { label: 'Кузов', value: filterOptionLabel(d.body_type, 'bodyType') },
            ].concat(driveVal ? [{ label: 'Привод', value: driveVal }] : []).concat(
                { label: 'VIN', value: d.vin },
                { label: 'Кол-во мест', value: d.seatCount },
                { label: 'Объём двигателя', value: (function() {
                    var raw = d.displacement || d.engine_volume || d.engineDisplacement || d.dongchedi_displacement_label || '';
                    if (raw == null || raw === '') return '';
                    var s = String(raw).trim();
                    if (!s) return '';
                    var num = parseInt(s.replace(/[^\d]/g, ''), 10);
                    if (!isNaN(num) && num >= 800 && num <= 8000 && !/[tT]/.test(s)) {
                        return num.toLocaleString('ru-RU') + ' см³';
                    }
                    return s;
                })() },
            ).concat(powerVal ? [{ label: 'Мощность', value: powerVal }] : []).concat(
                d.city ? [{ label: 'Город / регион (КНР)', value: d.city }] : []
            ).concat(
                d.transfer_count != null && d.transfer_count !== '' ? [{ label: 'Перерегистраций (КНР)', value: String(d.transfer_count) }] : []
            ).concat(
                d.interior_color ? [{ label: 'Цвет салона', value: d.interior_color }] : []
            );
            var specHtml = '<div class="detail-section"><h2>Основные характеристики</h2><div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-0">';
            specs.forEach(function(s) {
                if (s.value) specHtml += '<div class="dotted-pair"><span class="key">' + s.label + '</span><span class="value">' + s.value + '</span></div>';
            });
            specHtml += '</div></div>';
            if (d.dongchedi_summary) {
                var sumTxt = String(d.dongchedi_summary).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                specHtml += '<div class="detail-section"><h2>Сводка на площадке</h2><p class="text-sm opacity-90">' + sumTxt + '</p></div>';
            }

            const optionsHtml = renderOptionsGrouped(d.options?.standard || []);
            const bodyPanelsHtml = renderBodyPanels(insp.bodyPanels);
            const commentsHtml = renderComments(insp.bodyComments);
            const additionalHtml = (insp.additional && Object.keys(insp.additional).length)
                ? `<div class="card"><h2 class="card-title">Дополнительная информация</h2><table class="w-full text-sm data-table">${Object.entries(insp.additional).map(([k,v])=>`<tr><td>${k}</td><td>${v}</td></tr>`).join('')}</table></div>` : '';
            const bodyChangedHtml = (insp.bodyChanged && Object.keys(insp.bodyChanged).length)
                ? `<div class="card"><h2 class="card-title">Заменённые/покрашенные детали</h2><table class="w-full text-sm data-table">${Object.entries(insp.bodyChanged).map(([k,v])=>`<tr><td>${partNamesRu[k] || k}</td><td>${statusRu[v] || v}</td></tr>`).join('')}</table></div>` : '';

            const conditionDiagramHtml = renderConditionDiagram(rawData, extra.diagnosis_photos || []);
            window.diagnosisPhotosForModal = (extra.diagnosis_photos || []).filter(function(url) { return typeof url === 'string' && url.trim() !== ''; }).slice(0, 5).map(function(url) { return { path: url }; });
            const inspectionCombinedHtml = renderInspectionCombined(insp);

            let recordHtml = '';
            if (extra.record_open) {
                const r = extra.record_open;
                var historyPairs = [
                    { label: 'Гос. номер', value: r.carNo || '—' },
                    { label: 'Первая регистрация', value: r.firstDate || '—' },
                    { label: 'Топливо', value: filterOptionLabel(r.fuel, 'engineType') || '—' },
                    { label: 'Кузов', value: filterOptionLabel(r.carShape, 'bodyType') || '—' },
                    { label: 'Количество владельцев', value: r.ownerChangeCnt ?? '0' },
                    { label: 'Мои аварии (кол-во)', value: r.myAccidentCnt ?? '0' },
                    { label: 'Аварии с другими', value: r.otherAccidentCnt ?? '0' },
                    { label: 'Угон', value: r.robberCnt ?? '0' },
                    { label: 'Тотал', value: r.totalLossCnt ?? '0' },
                    { label: 'Потоп', value: r.floodTotalLossCnt ?? '0' },
                    { label: 'Залог', value: r.loan ?? '0' },
                    { label: 'Гос.средства', value: r.government ?? '0' }
                ];
                var historyDataHtml = historyPairs.map(function(p) { return '<div class="dotted-pair"><span class="key">' + p.label + '</span><span class="value">' + p.value + '</span></div>'; }).join('');
                const hasAccidents = r.accidents && r.accidents.length > 0;
                recordHtml = '<div class="history-wrap"><h2 class="history-main-title">История автомобиля</h2>';
                recordHtml += '<div class="history-headers-grid">';
                recordHtml += '<button type="button" class="history-group-header is-active" data-history-index="0" aria-expanded="true" aria-controls="history-body-0" id="history-header-0">Основные данные</button>';
                if (hasAccidents) recordHtml += '<button type="button" class="history-group-header" data-history-index="1" aria-expanded="false" aria-controls="history-body-1" id="history-header-1">Детали ДТП <span class="history-tab-badge">' + r.accidents.length + '</span></button>';
                recordHtml += '</div><div class="history-panel">';
                recordHtml += '<div class="history-group-body is-visible" id="history-body-0" role="region" aria-labelledby="history-header-0"><div class="history-data-grid">' + historyDataHtml + '</div></div>';
                if (hasAccidents) {
                    var krwPerUsdt = d.krw_per_usdt || 1400;
                    var usdtRub = d.usdt_rub || 95;
                    var rubPerWon = usdtRub / krwPerUsdt;
                    recordHtml += '<div class="history-group-body" id="history-body-1" role="region" aria-labelledby="history-header-1">';
                    r.accidents.forEach(acc => {
                        var typeText = accidentTypeLabels[String(acc.type)] || acc.type || '—';
                        recordHtml += '<div class="accident-card"><div class="history-accident-grid">';
                        recordHtml += '<div><span class="history-accident-label">Дата</span>' + (acc.date || '—') + '</div>';
                        recordHtml += '<div><span class="history-accident-label">Тип</span>' + typeText + '</div>';
                        recordHtml += '<div><span class="history-accident-label">Страховая выплата</span>' + formatWonToRub(acc.insuranceBenefit, rubPerWon) + '</div>';
                        recordHtml += '<div><span class="history-accident-label">Запчасти</span>' + formatWonToRub(acc.partCost, rubPerWon) + '</div>';
                        recordHtml += '<div><span class="history-accident-label">Работы</span>' + formatWonToRub(acc.laborCost, rubPerWon) + '</div>';
                        recordHtml += '<div><span class="history-accident-label">Покраска</span>' + formatWonToRub(acc.paintingCost, rubPerWon) + '</div>';
                        recordHtml += '</div></div>';
                    });
                    recordHtml += '</div>';
                }
                recordHtml += '</div></div>';
            }

            // Правая колонка
            const priceColumnHtml = renderPriceColumn(rawData);

            // Галерея — отдельным блоком сверху (3/4 страницы, миниатюры справа). Ниже — сетка: инфо слева, правое меню справа.
            const leftColumnContent = [];
            leftColumnContent.push(`<div id="basic-info">${specHtml}</div>`);
            leftColumnContent.push(`<div id="options">${optionsHtml}</div>`);

            // Блок диагностики (объединяем все поддиагностики + схема кузова)
            let inspectionHtml = '';
            if (bodyPanelsHtml || commentsHtml || additionalHtml || bodyChangedHtml || inspectionCombinedHtml || conditionDiagramHtml) {
                inspectionHtml = '<div id="inspection">';
                if (conditionDiagramHtml) inspectionHtml += conditionDiagramHtml;
                if (bodyPanelsHtml) inspectionHtml += bodyPanelsHtml;
                if (commentsHtml) inspectionHtml += commentsHtml;
                if (additionalHtml) inspectionHtml += additionalHtml;
                if (bodyChangedHtml) inspectionHtml += bodyChangedHtml;
                if (inspectionCombinedHtml) inspectionHtml += inspectionCombinedHtml;
                inspectionHtml += '</div>';
            }
            if (inspectionHtml) leftColumnContent.push(inspectionHtml);

            if (recordHtml) leftColumnContent.push(`<div id="history">${recordHtml}</div>`);

            const leftColumnHtml = leftColumnContent.join('');

            container.setAttribute('aria-busy', 'false');
            container.innerHTML = `
                ${galleryHtml}
                <div class="details-layout">
                    <div class="details-left space-y-8">
                        ${leftColumnHtml}
                    </div>
                    <div class="details-right space-y-6">
                        ${priceColumnHtml}
                    </div>
                </div>
            `;

            var favButton = container.querySelector('.order-icon-favourite');
            var currentCarId = rawData.id != null ? rawData.id : (rawData.inner_id != null ? rawData.inner_id : ((d && d.inner_id != null) ? d.inner_id : null));
            if (favButton && currentCarId != null && window.WRAAuthFavorites) {
                window.WRAAuthFavorites.bindFavoriteButton(favButton, currentCarId);
                window.WRAAuthFavorites.addHistory(currentCarId);
            }

            bindWraChannelExportButton(rawData);

            // Тултипы для бейджей и info в правой колонке (как в index.html)
            (function initOrderCardTooltips() {
                var orderCard = document.getElementById('orderCard');
                if (!orderCard) return;
                var tooltip = document.createElement('div');
                tooltip.className = 'order-tooltip';
                document.body.appendChild(tooltip);
                orderCard.querySelectorAll('.info-icon-wrap[data-tooltip]').forEach(function(wrap) {
                    var text = wrap.getAttribute('data-tooltip') || '';
                    if (!text) return;
                    wrap.addEventListener('mouseenter', function() {
                        tooltip.textContent = text;
                        tooltip.style.display = 'block';
                        var rect = wrap.getBoundingClientRect();
                        var tw = tooltip.offsetWidth;
                        tooltip.style.left = Math.max(8, rect.left + rect.width / 2 - tw / 2) + 'px';
                        tooltip.style.top = (rect.top - tooltip.offsetHeight - 8) + 'px';
                    });
                    wrap.addEventListener('mouseleave', function() { tooltip.style.display = 'none'; });
                });
            })();

            // Динамическое обновление шапки навигации
            updateHeaderNavigation();

            // Фото диагностики: скелетон до загрузки, открытие в модалке
            document.querySelectorAll('.diag-photo').forEach(function(el) {
                var i = parseInt(el.getAttribute('data-diag-index'), 10);
                if (!isNaN(i) && window.diagnosisPhotosForModal && window.diagnosisPhotosForModal.length) {
                    el.addEventListener('click', function() { openModal(i, window.diagnosisPhotosForModal); });
                    el.addEventListener('keydown', function(e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openModal(i, window.diagnosisPhotosForModal); } });
                }
            });
            document.querySelectorAll('.diag-photo-img').forEach(function(img) {
                function show() { img.classList.add('diag-loaded'); }
                if (img.complete) show(); else img.addEventListener('load', show);
            });

            // Блок "Похожие по цене" — ленивая загрузка при скролле до него
            var similarPlaceholder = document.createElement('div');
            similarPlaceholder.id = 'similar-cars-placeholder';
            similarPlaceholder.className = 'similar-cars-placeholder';
            similarPlaceholder.setAttribute('aria-hidden', 'true');
            container.appendChild(similarPlaceholder);

            var similarObserver = new IntersectionObserver(function(entries) {
                var entry = entries[0];
                if (!entry || !entry.isIntersecting) return;
                similarObserver.disconnect();
                similarPlaceholder.textContent = 'Загрузка...';
                renderSimilarCars(rawData, { lazy: true }).then(function(html) {
                    if (!similarPlaceholder.parentNode) return;
                    if (html) {
                        var wrap = document.createElement('div');
                        wrap.innerHTML = html;
                        var section = wrap.firstElementChild;
                        if (section) {
                            similarPlaceholder.parentNode.replaceChild(section, similarPlaceholder);
                            setupSimilarCarsImageSkeleton(section);
                        }
                    } else {
                        similarPlaceholder.remove();
                    }
                    setupSectionNavigation();
                }).catch(function() {
                    if (similarPlaceholder.parentNode) {
                        similarPlaceholder.textContent = '';
                        similarPlaceholder.remove();
                    }
                });
            }, { rootMargin: '480px', threshold: 0 });
            similarObserver.observe(similarPlaceholder);

            const datePlaceholder = document.getElementById('data-date-placeholder');
            if (datePlaceholder) {
                const dateSource = d.created_at || rawData.created_at;
                if (dateSource) {
                    const formatted = new Date(dateSource).toLocaleDateString('ru-RU');
                    datePlaceholder.textContent = formatted;
                }
            }

            // Счётчик просмотров объявления (на основе localStorage, только первое открытие)
            try {
                const viewsKey = `encar_views_${rawData.id || rawData.inner_id || d.inner_id || 'unknown'}`;
                const stored = window.localStorage ? window.localStorage.getItem(viewsKey) : null;
                let views = stored ? parseInt(stored, 10) || 0 : 0;
                // Если просмотров ещё не было в этом браузере, записываем первое открытие
                if (!stored && window.localStorage) {
                    views = 1;
                    window.localStorage.setItem(viewsKey, String(views));
                }
                const viewsLabel = document.getElementById('galleryViewsLabel');
                if (viewsLabel) {
                    viewsLabel.textContent = `${views.toLocaleString('ru-RU')} просмотров`;
                }
            } catch (e) {
                // localStorage может быть недоступен, тогда просто игнорируем
            }

            // ---------- Инициализация обработчиков галереи ----------
            const mainPhoto = document.getElementById('mainPhoto');
            const galleryMain = document.getElementById('galleryMain');
            const galleryCounter = document.getElementById('galleryCounter');
            const thumbnailsRow = document.getElementById('thumbnailsRow');
            if (!mainPhoto || !galleryMain) return;

            let currentIdx = 0;

            function buildThumbUrl(p) {
                return getModalThumbUrl(p);
            }

            function buildMainPhotoUrl(idx) {
                if (idx < 0 || idx >= photosArray.length) return '';
                return getModalMainUrl(photosArray[idx]);
            }

            function prefetchGalleryFullSize(idx) {
                if (idx < 0 || idx >= photosArray.length) return;
                var u = buildMainPhotoUrl(idx);
                if (!u) return;
                var im = new Image();
                im.decoding = 'async';
                im.src = u;
            }

            function renderThumbnailsWindow(centerIndex) {
                if (!thumbnailsRow || !photosArray.length) return;
                const len = photosArray.length;
                // В миниатюрах не показываем текущее главное фото (чтобы не было дубля)
                const shown = Math.min(3, Math.max(0, len - 1));
                let html = '';
                for (let k = 0; k < shown; k++) {
                    const idx = (centerIndex + 1 + k) % len;
                    const p = photosArray[idx];
                    html += `<button type="button" class="thumbnail" data-index="${idx}" aria-label="Миниатюра ${idx+1}"><img src="${buildThumbUrl(p)}" alt="Миниатюра ${idx+1}"></button>`;
                }
                // "+N фото" показываем только если после текущего + показанных ещё что-то остаётся
                const remaining = len - 1 - shown;
                if (remaining > 0) {
                    const moreIdx = (centerIndex + 1 + shown) % len;
                    const moreP = photosArray[moreIdx];
                    html += `<button type="button" class="thumbnail more" data-index="more" aria-label="Открыть все фотографии">
                        <img src="${buildThumbUrl(moreP)}" alt="Дополнительные фото">
                        <span>+${remaining} фото</span>
                    </button>`;
                }
                thumbnailsRow.innerHTML = html;
                // Показывать миниатюры только после загрузки — при быстром перелистывании не видно «бэка»
                thumbnailsRow.querySelectorAll('.thumbnail img').forEach(function (img) {
                    function show() { img.classList.add('thumb-loaded'); }
                    if (img.complete) show(); else img.addEventListener('load', show);
                });
            }

            function updateMainPhoto(index) {
                if (index < 0) index = photosArray.length - 1;
                if (index >= photosArray.length) index = 0;
                currentIdx = index;
                const imgUrl = buildMainPhotoUrl(index);
                mainPhoto.src = imgUrl;
                try { mainPhoto.fetchPriority = 'high'; } catch (e0) {}
                galleryCounter.textContent = (index+1) + '/' + photosArray.length;
                renderThumbnailsWindow(index);
                prefetchGalleryFullSize(index - 1);
                prefetchGalleryFullSize(index + 1);
                prefetchGalleryFullSize(index + 2);
            }

            mainPhoto.addEventListener('load', function() { mainPhoto.classList.add('main-photo-loaded'); });
            if (mainPhoto.complete) mainPhoto.classList.add('main-photo-loaded');

            let dragStartX = null;
            let dragging = false;
            const dragThreshold = 40;

            galleryMain.addEventListener('pointerdown', (e) => {
                dragStartX = e.clientX;
                dragging = true;
            });

            galleryMain.addEventListener('pointerup', (e) => {
                if (e.target.closest('.gallery-main-prev') || e.target.closest('.gallery-main-next')) return;
                if (!dragging || dragStartX === null) {
                    return;
                }
                const dx = e.clientX - dragStartX;
                dragging = false;
                dragStartX = null;

                if (Math.abs(dx) > dragThreshold) {
                    if (dx < 0) {
                        updateMainPhoto(currentIdx + 1);
                    } else {
                        updateMainPhoto(currentIdx - 1);
                    }
                } else {
                    var rect = galleryMain.getBoundingClientRect();
                    var x = e.clientX - rect.left;
                    var w = rect.width;
                    if (w > 0) {
                        if (x < w * 0.3) updateMainPhoto(currentIdx - 1);
                        else if (x > w * 0.7) updateMainPhoto(currentIdx + 1);
                        else openModal(currentIdx);
                    } else {
                        openModal(currentIdx);
                    }
                }
            });

            thumbnailsRow.addEventListener('click', (e) => {
                const thumb = e.target.closest('.thumbnail');
                if (!thumb) return;
                const index = thumb.dataset.index;
                if (index === 'more') {
                    openModal(currentIdx);
                } else {
                    updateMainPhoto(parseInt(index, 10));
                }
            });
            var galleryMainPrev = document.getElementById('galleryMainPrev');
            var galleryMainNext = document.getElementById('galleryMainNext');
            if (galleryMainPrev) galleryMainPrev.addEventListener('click', function(e) { e.preventDefault(); e.stopPropagation(); updateMainPhoto(currentIdx - 1); });
            if (galleryMainNext) galleryMainNext.addEventListener('click', function(e) { e.preventDefault(); e.stopPropagation(); updateMainPhoto(currentIdx + 1); });

            // Первичная отрисовка миниатюр и предзагрузка соседних кадров
            renderThumbnailsWindow(currentIdx);
            prefetchGalleryFullSize(1);
            if (photosArray.length > 2) prefetchGalleryFullSize(photosArray.length - 1);
        }

        // ---------- Функция для динамического обновления шапки ----------
        function updateHeaderNavigation() {
            const gnb = document.querySelector('.gnb');
            if (!gnb) return;

            // Определяем, какие секции присутствуют на странице
            const sections = [
                { id: 'basic-info', label: 'Основная информация' },
                { id: 'options', label: 'Опции' },
                { id: 'inspection', label: 'Диагностика' },
                { id: 'history', label: 'История' },
                { id: 'diagnostics', label: 'Фото диагностики' }
            ];

            // Очищаем текущее меню
            gnb.innerHTML = '';

            // Добавляем только те секции, которые присутствуют на странице
            sections.forEach(section => {
                const element = document.getElementById(section.id);
                if (element) {
                    const li = document.createElement('li');
                    const a = document.createElement('a');
                    a.href = `#${section.id}`;
                    a.innerHTML = `<b>${section.label}</b>`;
                    a.addEventListener('click', (e) => {
                        e.preventDefault();
                        const header = document.querySelector('.header');
                        const targetPosition = element.getBoundingClientRect().top + window.scrollY - (header ? header.offsetHeight : 0);
                        window.scrollTo({
                            top: targetPosition,
                            behavior: 'smooth'
                        });
                    });
                    li.appendChild(a);
                    gnb.appendChild(li);
                }
            });

            // Делаем первую ссылку активной по умолчанию
            const firstLink = gnb.querySelector('a');
            if (firstLink) {
                firstLink.classList.add('on');
            }
        }

        // ---------- Анимации навигации ----------
        function setupSectionNavigation() {
            const navLinks = document.querySelectorAll('.gnb a');
            const header = document.querySelector('.header');
            if (!navLinks.length || !header) return;

            const sections = [];
            navLinks.forEach(link => {
                const targetId = link.getAttribute('href').substring(1);
                const targetElement = document.getElementById(targetId);
                if (targetElement) {
                    sections.push({
                        id: targetId,
                        element: targetElement,
                        link: link
                    });
                }
            });

            if (sections.length === 0) return;

            // Плавный скролл при клике
            navLinks.forEach(link => {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    const targetId = link.getAttribute('href').substring(1);
                    const targetElement = document.getElementById(targetId);
                    if (targetElement) {
                        const headerHeight = header.offsetHeight;
                        const targetPosition = targetElement.getBoundingClientRect().top + window.scrollY - headerHeight;
                        window.scrollTo({
                            top: targetPosition,
                            behavior: 'smooth'
                        });
                    }
                });
            });

            // Intersection Observer для подсветки активного раздела
            const observerOptions = {
                root: null,
                rootMargin: `-${header.offsetHeight}px 0px 0px 0px`,
                threshold: 0.2
            };

            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const id = entry.target.getAttribute('id');
                        const activeLink = document.querySelector(`.gnb a[href="#${id}"]`);
                        if (activeLink) {
                            navLinks.forEach(link => link.classList.remove('on'));
                            activeLink.classList.add('on');
                        }
                    }
                });
            }, observerOptions);

            sections.forEach(section => observer.observe(section.element));
        }

        // Аккордеон: Опции (вертикальный), Инспекция (вкладки), История (вертикальный) — делегирование
        document.getElementById('car-content').addEventListener('click', function(e) {
            var optHeader = e.target.closest('.option-accordion-header');
            if (optHeader) {
                e.preventDefault();
                var item = optHeader.closest('.option-accordion-item');
                if (!item) return;
                var isOpen = item.classList.toggle('is-open');
                optHeader.setAttribute('aria-expanded', isOpen);
                return;
            }
            var inspHeader = e.target.closest('.inspection-group-header');
            if (inspHeader) {
                e.preventDefault();
                var inspBlock = inspHeader.closest('.inspection-block');
                if (!inspBlock) return;
                var index = inspHeader.getAttribute('data-inspection-index');
                if (index == null) return;
                inspBlock.querySelectorAll('.inspection-group-header').forEach(function(h) { h.classList.remove('is-active'); h.setAttribute('aria-expanded', 'false'); });
                inspBlock.querySelectorAll('.inspection-group-body').forEach(function(b) { b.classList.remove('is-visible'); });
                inspHeader.classList.add('is-active');
                inspHeader.setAttribute('aria-expanded', 'true');
                var bodies = inspBlock.querySelectorAll('.inspection-group-body');
                var body = bodies[parseInt(index, 10)];
                if (body) body.classList.add('is-visible');
                return;
            }
            var histHeader = e.target.closest('.history-group-header');
            if (histHeader) {
                e.preventDefault();
                var wrap = histHeader.closest('.history-wrap');
                if (!wrap) return;
                var index = histHeader.getAttribute('data-history-index');
                if (index == null) return;
                wrap.querySelectorAll('.history-group-header').forEach(function(h) { h.classList.remove('is-active'); h.setAttribute('aria-expanded', 'false'); });
                wrap.querySelectorAll('.history-group-body').forEach(function(b) { b.classList.remove('is-visible'); });
                histHeader.classList.add('is-active');
                histHeader.setAttribute('aria-expanded', 'true');
                var body = wrap.querySelector('#history-body-' + index);
                if (body) body.classList.add('is-visible');
            }
        });

        // ---------- Загрузка данных ----------
        function wraGetCarIdFromUrl() {
            try {
                var q = new URLSearchParams(window.location.search || '').get('id');
                if (q && String(q).trim()) return String(q).trim();
            } catch (e0) {}
            try {
                var path = window.location.pathname || '';
                var m = path.match(/\/detail\/([^/]+)\/?$/);
                if (m && m[1]) return decodeURIComponent(m[1]);
            } catch (e1) {}
            return null;
        }
        const carId = wraGetCarIdFromUrl();
        if (carId) {
            window.__wraSimilarCarsPromise = fetch(apiUrl('/api/similar?car_id=' + encodeURIComponent(carId) + '&limit=8'))
                .then(function(r) { return r.ok ? r.json() : null; })
                .catch(function() { return null; });
        }
        if (!carId) {
            var el = document.getElementById('car-content');
            if (el) { el.setAttribute('aria-busy', 'false'); el.innerHTML = '<div class="bg-white rounded-2xl shadow-sm border border-gray-200 p-10 text-center"><p class="text-gray-600 mb-4">Не указан ID автомобиля.</p><a href="/catalog" class="inline-flex items-center justify-center px-6 py-3 rounded-full font-semibold text-white bg-gray-800 hover:bg-gray-900">В каталог</a></div>'; }
            return;
        }

        function tryFetch(url) {
            return fetch(url).then(function(response) {
                if (!response.ok) throw new Error('Ошибка загрузки данных');
                return response.json();
            });
        }

        /** Один автомобиль с бэкенда (без скачивания полного cars.json — при ~180k строк браузер не справляется). */
        function loadCarDataFromApi(id) {
            return fetch(apiUrl('/api/car/' + encodeURIComponent(id)), { cache: 'no-store' }).then(function(response) {
                if (response.status === 404) {
                    return Promise.reject({ notFound: true });
                }
                if (response.status === 429) {
                    return Promise.reject({ status: 429, rateLimit: true });
                }
                if (response.status === 401 || response.status === 403) {
                    return Promise.reject({ status: response.status, forbidden: true });
                }
                if (!response.ok) throw new Error('Ошибка загрузки данных');
                return response.json();
            }).then(function(data) {
                var r = data && data.result;
                if (r && typeof r === 'object' && !Array.isArray(r)) return r;
                throw new Error('unexpected shape');
            });
        }

        /** Фолбэк для статики / без API (маленький cars.json). */
        function loadCarDataFromCarsJson(id) {
            var carsJsonHref = new URL('/cars.json', window.location.origin).href;
            return tryFetch(carsJsonHref).then(function(data) {
                var cars = data.result || [];
                if (!Array.isArray(cars)) cars = [];
                var carData = cars.find(function(item) {
                    return String(item.id) === String(id) || String(item.inner_id) === String(id) || String((item.data && item.data.inner_id) || '') === String(id);
                });
                if (!carData) return Promise.reject({ notFound: true });
                return carData;
            });
        }

        function loadCarData(id) {
            return loadCarDataFromApi(id).catch(function(err) {
                if (err && err.notFound) return Promise.reject(err);
                if (err && (err.rateLimit || err.forbidden)) return Promise.reject(err);
                if (!allowCarPageJsonFallback()) return Promise.reject(err);
                return loadCarDataFromCarsJson(id);
            });
        }

        var engineMapUrl = new URL('/data/engine_map.json', window.location.origin).href;
        Promise.all([
            loadCarData(carId),
            fetch(engineMapUrl).then(function(r) { return r.ok ? r.json() : null; }).catch(function() { return null; })
        ]).then(function(results) {
                buildMotorHpIndexCar(results[1]);
                renderCar(results[0]);
                try {
                    var raw = results[0];
                    var rid =
                        raw &&
                        (raw.id != null
                            ? String(raw.id)
                            : raw.inner_id != null
                              ? String(raw.inner_id)
                              : raw.data && raw.data.inner_id != null
                                ? String(raw.data.inner_id)
                                : '');
                    if (rid) {
                        if (window.WRAContextBar && typeof window.WRAContextBar.addRecent === 'function') {
                            window.WRAContextBar.addRecent(rid);
                        }
                        if (window.WRAAnalytics && typeof window.WRAAnalytics.track === 'function') {
                            window.WRAAnalytics.track('wra_car_view', { id: rid });
                        }
                    }
                } catch (eRv) {}
            })
            .catch(function(err) {
                console.error(err);
                var el = document.getElementById('car-content');
                if (el) {
                    el.setAttribute('aria-busy', 'false');
                    var msg = 'Не удалось загрузить данные. Проверьте подключение к интернету.';
                    if (err && err.notFound) {
                        msg = 'Автомобиль с таким ID не найден.';
                    } else if (err && err.rateLimit) {
                        msg = 'Слишком много запросов к серверу. Подождите минуту и обновите страницу.';
                    } else if (err && err.forbidden) {
                        msg = 'Доступ к данным ограничен. Попробуйте позже или войдите в аккаунт.';
                    }
                    el.innerHTML =
                        '<div class="bg-white rounded-2xl shadow-sm border border-gray-200 p-10 text-center"><p class="text-gray-600 mb-4">' +
                        String(msg).replace(/</g, '&lt;') +
                        '</p><a href="/catalog" class="inline-flex items-center justify-center px-6 py-3 rounded-full font-semibold text-white bg-gray-800 hover:bg-gray-900">В каталог</a></div>';
                }
            });

        // Обработчики модалки
        var modalCloseEl = document.getElementById('modalClose');
        var modalPrevEl = document.getElementById('modalPrev');
        var modalNextEl = document.getElementById('modalNext');
        var galleryModalEl = document.getElementById('galleryModal');
        if (modalCloseEl) modalCloseEl.addEventListener('click', closeModal);
        if (modalPrevEl) modalPrevEl.addEventListener('click', function() { currentPhotoIndex--; updateModal(); });
        if (modalNextEl) modalNextEl.addEventListener('click', function() { currentPhotoIndex++; updateModal(); });
        window.addEventListener('click', function(e) {
            if (galleryModalEl && e.target === galleryModalEl) closeModal();
        });
        document.addEventListener('keydown', function(e) {
            var modal = document.getElementById('galleryModal');
            if (!modal || !modal.classList.contains('active')) return;
            if (e.key === 'Escape') {
                closeModal();
            } else if (e.key === 'ArrowRight') {
                currentPhotoIndex++;
                updateModal();
            } else if (e.key === 'ArrowLeft') {
                currentPhotoIndex--;
                updateModal();
            }
        });
        function handleConditionZoneTap(e) {
            var galleryModal = document.getElementById('galleryModal');
            if (galleryModal && galleryModal.classList.contains('active')) return;
            var carContent = document.getElementById('car-content');
            if (!carContent || !carContent.contains(e.target)) return;
            var zone = e.target.closest('.condition-zone');
            if (zone) {
                zone.classList.toggle('tooltip-visible');
                carContent.querySelectorAll('.condition-zone.tooltip-visible').forEach(function(z) {
                    if (z !== zone) z.classList.remove('tooltip-visible');
                });
            } else {
                carContent.querySelectorAll('.condition-zone.tooltip-visible').forEach(function(z) {
                    z.classList.remove('tooltip-visible');
                });
            }
        }
        document.addEventListener('click', handleConditionZoneTap);
        document.addEventListener('touchend', function(e) {
            if ('ontouchstart' in window) handleConditionZoneTap(e);
        }, { passive: true });
    })();
