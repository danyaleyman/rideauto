import logging
import os
import re
import hashlib
import threading
import requests
import json
import time
from urllib.parse import urlencode
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path

from encar_price_intent import classify_encar_price_intent, price_signals_json
from clean_layers import build_catalog_clean_layers
from raw_json_contract import validate_raw_json_min_contract

logger = logging.getLogger(__name__)
PARSER_SCHEMA_VERSION = "encar.v2"


def _normalize_proxy_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    if not u.startswith("http"):
        u = "http://" + u
    return u


def _proxy_urls_from_scraper_config() -> List[str]:
    """Те же URL, что у async-скрапера (scraper_config.yaml → proxy.urls)."""
    try:
        import yaml
    except ImportError:
        return []
    path = Path(__file__).resolve().parent.parent / "scraper_config.yaml"
    if not path.is_file():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        return []
    px = cfg.get("proxy") or {}
    if not px.get("enabled"):
        return []
    urls = px.get("urls") or []
    out = [_normalize_proxy_url(str(u)) for u in urls if u]
    return [u for u in out if u]


def collect_encar_proxy_urls() -> List[str]:
    """
    Список HTTP(S) прокси для ротации (каждый запрос — следующий).
    Приоритет: ENCAR_PROXY_URLS (разделители , ; | перевод строки) → ENCAR_PROXY_URL
    → ENCAR_PROXY_SERVER+USER+PASSWORD → scraper_config.yaml proxy.urls
    """
    raw = os.environ.get("ENCAR_PROXY_URLS", "").strip()
    if raw:
        return [
            _normalize_proxy_url(x)
            for x in re.split(r"[\n,;|]+", raw)
            if x.strip()
        ]
    url = os.environ.get("ENCAR_PROXY_URL", "").strip()
    if url:
        return [_normalize_proxy_url(url)]
    server = os.environ.get("ENCAR_PROXY_SERVER", "").strip()
    if server:
        if not server.startswith("http"):
            server = "http://" + server
        user = os.environ.get("ENCAR_PROXY_USER", "")
        password = os.environ.get("ENCAR_PROXY_PASSWORD", "")
        if user and password:
            from urllib.parse import quote_plus

            auth = f"{quote_plus(user)}:{quote_plus(password)}"
            scheme, rest = server.split("://", 1)
            full = f"{scheme}://{auth}@{rest}"
            return [_normalize_proxy_url(full)]
        return [_normalize_proxy_url(server)]
    return _proxy_urls_from_scraper_config()


class EncarFullParser:
    def __init__(self):
        self.session = requests.Session()
        self._proxy_urls: List[str] = collect_encar_proxy_urls()
        self._proxy_index = 0
        if self._proxy_urls:
            self._apply_next_proxy()
            logger.info("Encar parser: ротационный прокси, %d URL", len(self._proxy_urls))
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9,ru-RU;q=0.8,ru;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'X-Requested-With': 'XMLHttpRequest',
        })

        # Базовые URL
        self.list_url = 'https://api.encar.com/search/car/list/general'
        self.base_api = 'https://api.encar.com/v1/readside'

        # Эндпоинты
        self.vehicle_detail_url = f'{self.base_api}/vehicle/{{}}'
        self.record_url = f'{self.base_api}/record/vehicle/{{}}/open'
        self.diagnosis_url = f'{self.base_api}/diagnosis/vehicle/{{}}'
        self.sellingpoint_url = f'{self.base_api}/diagnosis/vehicle/{{}}/sellingpoint'
        self.user_url = f'{self.base_api}/user/{{}}'
        # Добавляем эндпоинт для полной инспекции
        self.inspection_url = f'{self.base_api}/inspection/vehicle/{{}}'
        self._power_lookup: Optional[Dict[str, Any]] = None
        self._lookup_lock = threading.Lock()
        self.lookup_path = Path(__file__).resolve().parent.parent / "data" / "car_power_lookup.json"
        self._power_stats = {"with_power": 0, "without_power": 0}

    def _apply_next_proxy(self) -> None:
        if not self._proxy_urls:
            return
        u = self._proxy_urls[self._proxy_index % len(self._proxy_urls)]
        self._proxy_index += 1
        self.session.proxies.clear()
        self.session.proxies.update({"http": u, "https": u})

    def _session_get(self, url: str, **kwargs) -> Any:
        if self._proxy_urls:
            self._apply_next_proxy()
        return self.session.get(url, **kwargs)

    def _get_power_lookup(self) -> Dict[str, Any]:
        """Загружает lookup-файл с данными о мощности (ключи: производитель|модель|бейдж и др.)."""
        with self._lookup_lock:
            if self._power_lookup is not None:
                return self._power_lookup
            if not self.lookup_path.exists():
                self._power_lookup = {}
                return self._power_lookup
            try:
                with open(self.lookup_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._power_lookup = data if isinstance(data, dict) else {}
            except Exception as e:
                logger.warning("Ошибка чтения lookup-файла %s: %s", self.lookup_path, e)
                self._power_lookup = {}
            return self._power_lookup

    def _save_lookup(self, lookup_data: Dict[str, Any]) -> None:
        """Сохраняет lookup-файл с данными о мощности."""
        with self._lookup_lock:
            try:
                self.lookup_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = self.lookup_path.with_suffix(self.lookup_path.suffix + ".tmp")
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(lookup_data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.lookup_path)
                self._power_lookup = lookup_data
            except Exception as e:
                logger.warning("Ошибка сохранения lookup-файла %s: %s", self.lookup_path, e)

    # ---------- Построение URL фото ----------
    def build_carphoto_url(self, photo: dict, now: str) -> str:
        path = photo.get('path')
        update_time = photo.get('updateDateTime', now)

        if not path:
            return ''

        if path.startswith('/'):
            new_path = "carpicture" + path
        else:
            new_path = "carpicture/" + path

        params = {
            'impolicy': 'heightRate',
            'rh': '696',
            'cw': '1160',
            'ch': '696',
            'cg': 'Center',
            'wtmk': 'https://ci.encar.com/wt_mark/w_mark_04.png',
        }

        if update_time:
            t = re.sub(r'\D', '', update_time)[:14]
            params['t'] = t

        return f"https://ci.encar.com/{new_path}?{urlencode(params)}"

    # ---------- Определение привода ----------
    def _normalize_drive_type_from_api(self, raw: Any) -> str:
        """Приводит значение DriveType/driveType из API к одному из: AWD, 2WD, FWD, RWD."""
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return ''
        s = str(raw).strip().upper()
        if not s:
            return ''
        if s in ('AWD', '4WD', '4X4', '4×4', 'FOURWHEEL', 'FOUR-WHEEL'):
            return 'AWD'
        if s in ('2WD', '2X2', 'TWOWHEEL', 'TWO-WHEEL'):
            return '2WD'
        if s in ('FWD', 'FF', 'FRONT'):
            return 'FWD'
        if s in ('RWD', 'FR', 'REAR'):
            return 'RWD'
        if 'AWD' in s or '4WD' in s or '4X4' in s or 'XDRIVE' in s or '4MATIC' in s or 'QUATTRO' in s or 'ALL4' in s:
            return 'AWD'
        if '2WD' in s:
            return '2WD'
        if 'FWD' in s or 'FRONT' in s:
            return 'FWD'
        if 'RWD' in s or 'REAR' in s:
            return 'RWD'
        return ''

    def _extract_drive_type(self, badge: str) -> str:
        """Извлекает тип привода из badge (название комплектации). Приоритет: AWD/4WD → 2WD → FWD → RWD."""
        if not badge or not isinstance(badge, str):
            return ''
        badge_upper = badge.upper()
        # 1) Точные маркеры полного привода
        awd_keywords = ['AWD', '4WD', '4X4', '4×4', 'XDRIVE', '4MATIC', 'ALL4', 'QUATTRO', 'Q4', '4MOTION', '4MATIC']
        for kw in awd_keywords:
            if kw in badge_upper:
                return 'AWD'
        # 2) Явный 2WD (перед или зад — по умолчанию 2WD)
        if '2WD' in badge_upper:
            return '2WD'
        # 3) Задний привод
        rwd_keywords = ['RWD', 'REAR', 'FR ', 'FR.', 'FRONT-ENGINE REAR']
        for kw in rwd_keywords:
            if kw in badge_upper:
                return 'RWD'
        # 4) Передний привод
        fwd_keywords = ['FWD', 'FRONT', 'FF ', 'FF.', 'FRONT-WHEEL']
        for kw in fwd_keywords:
            if kw in badge_upper:
                return 'FWD'
        return ''

    @staticmethod
    def _as_positive_float(value: Any) -> float:
        try:
            if value is None or value == '':
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _as_int(value: Any) -> Optional[int]:
        try:
            if value is None or value == "":
                return None
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, (int, float)):
                return int(value)
            raw = str(value).strip()
            if not raw:
                return None
            clean = re.sub(r"[^\d\-]", "", raw)
            if clean in {"", "-"}:
                return None
            return int(clean)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_text(value: Any) -> str:
        if value is None:
            return ""
        try:
            return str(value).strip()
        except Exception:
            return ""

    def _iter_path_values(self, obj: Any, prefix: str = ""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = f"{prefix}.{k}" if prefix else str(k)
                yield key, v
                yield from self._iter_path_values(v, key)
        elif isinstance(obj, list):
            for idx, v in enumerate(obj):
                key = f"{prefix}[{idx}]"
                yield key, v
                yield from self._iter_path_values(v, key)

    def _extract_numeric_by_key_hints(self, source: Any, key_hints: List[str]) -> Optional[int]:
        hints = [h.lower() for h in key_hints]
        values: List[int] = []
        for path, value in self._iter_path_values(source):
            p = path.lower()
            if any(h in p for h in hints):
                iv = self._as_int(value)
                if iv is not None:
                    values.append(iv)
        if not values:
            return None
        return max(values)

    def _extract_damage_summary(
        self,
        record: Optional[Dict[str, Any]],
        diagnosis: Optional[Dict[str, Any]],
        inspection_structured: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        insurance_cases = self._extract_numeric_by_key_hints(
            record,
            ["insurance_case", "insurancecase", "accident_count", "accidentcase"],
        )
        insurance_payout_krw = self._extract_numeric_by_key_hints(
            record,
            ["insurance_payout", "payout", "paid", "compensation", "claimamount"],
        )

        damaged_parts_count: Optional[int] = None
        if isinstance(inspection_structured, dict):
            body_changed = inspection_structured.get("bodyChanged")
            if isinstance(body_changed, dict):
                damaged_parts_count = len([k for k, v in body_changed.items() if k and v])
        if damaged_parts_count is None:
            panels = (diagnosis or {}).get("items") if isinstance(diagnosis, dict) else None
            if isinstance(panels, list):
                cnt = 0
                for item in panels:
                    if not isinstance(item, dict):
                        continue
                    result_code = str(item.get("resultCode") or item.get("resultCodeType") or "").upper()
                    result_raw = str(item.get("result") or "").strip().lower()
                    if result_code in {"REPLACEMENT", "PAINT", "REPAIR"} or result_raw in {"교체", "도장", "판금", "수리"}:
                        cnt += 1
                if cnt > 0:
                    damaged_parts_count = cnt

        return {
            "insurance_cases": insurance_cases if insurance_cases is not None else 0,
            "insurance_payout_krw": insurance_payout_krw if insurance_payout_krw is not None else 0,
            "damaged_parts_count": damaged_parts_count if damaged_parts_count is not None else 0,
        }

    @staticmethod
    def _shape_top_keys(payload: Any) -> List[str]:
        if not isinstance(payload, dict):
            return []
        return sorted(str(k) for k in payload.keys())

    def _source_shapes(
        self,
        item: Optional[Dict[str, Any]],
        detail: Optional[Dict[str, Any]],
        diagnosis: Optional[Dict[str, Any]],
        inspection: Optional[Dict[str, Any]],
        sellingpoint: Optional[Dict[str, Any]],
        record: Optional[Dict[str, Any]],
        user_info: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        shapes = {
            "list_item": self._shape_top_keys(item),
            "detail": self._shape_top_keys(detail),
            "diagnosis": self._shape_top_keys(diagnosis),
            "inspection": self._shape_top_keys(inspection),
            "sellingpoint": self._shape_top_keys(sellingpoint),
            "record": self._shape_top_keys(record),
            "user": self._shape_top_keys(user_info),
        }
        hashes: Dict[str, str] = {}
        for name, keys in shapes.items():
            digest = hashlib.sha1("|".join(keys).encode("utf-8")).hexdigest()[:12] if keys else ""
            hashes[name] = digest
        return {"keys": shapes, "hashes": hashes}

    def _is_monthly_finance_listing(self, item: Dict[str, Any]) -> bool:
        """
        Для части объявлений Encar в Price приходит ежемесячный платеж (월XX만원),
        а не полная цена продажи. Такие записи не должны участвовать в ценовом расчете.
        """
        if not isinstance(item, dict):
            return False
        payload = {
            "source": "encar",
            "price": item.get("Price"),
            "price_text": item.get("PriceView") or item.get("PriceText"),
            "encar_month_lease_price": item.get("MonthLeasePrice"),
            "encar_month_lease_rent_price": item.get("MonthLeaseRentPrice"),
            "encar_month_lease_rest": item.get("MonthLeaseRest"),
            "encar_lease_type": item.get("LeaseType"),
            "encar_attribute_type": item.get("AttributeType"),
            "encar_price_type": item.get("PriceType"),
            "encar_price_type_name": item.get("PriceTypeName"),
            "finance_type": item.get("FinanceType"),
        }
        intent, _ = classify_encar_price_intent(payload)
        return intent == "monthly_finance"

    def _extract_power_from_string(self, s: str) -> Optional[str]:
        """Извлекает мощность (л.с.) только из явных форм: 150마력, (180)hp. Не (992) — поколение."""
        if not s or not isinstance(s, str):
            return None
        s = s.strip()
        m = re.search(r'\(?\s*(\d{2,4})\s*\)?\s*마력', s)
        if m:
            return m.group(1)
        m = re.search(r'(\d{2,4})\s*hp\b', s, re.IGNORECASE)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def _normalize_power_to_hp(raw: Any) -> str:
        """
        Приводит значение мощности к л.с. (строка).
        API может отдавать: л.с. (20–2000), кВт (10–600), или строку типа "116.91".
        КВт обычно с дробной частью (116.91), л.с. — целые. Значения 1–19 отбрасываем.
        """
        if raw is None or raw == '':
            return ''
        try:
            s = str(raw).strip().replace(',', '.')
            n = float(re.sub(r'[^\d.]', '', s) or '0')
        except (ValueError, TypeError):
            return ''
        if n <= 0:
            return ''
        # По дробной части решаем: кВт (116.91) → переводим в л.с.; целое 159 → считаем л.с.
        is_likely_kw = isinstance(raw, float) and raw != int(raw)
        if not is_likely_kw and isinstance(raw, str):
            is_likely_kw = '.' in s and re.sub(r'[^\d.]', '', s) != ''
        if is_likely_kw and 10 <= n <= 600:
            hp = round(n * 1.35962)
            if 20 <= hp <= 2000:
                return str(hp)
        if 20 <= n <= 2000:
            return str(int(round(n)))
        return ''

    def get_power_stats(self) -> Dict[str, int]:
        """Статистика по мощности после парсинга: с мощностью / без."""
        return dict(self._power_stats)

    # ---------- Основные методы загрузки ----------
    def fetch_list_page(self, offset: int = 0, limit: int = 100, car_type: str = "for") -> Optional[Dict]:
        """
        Загружает страницу списка объявлений.

        car_type:
          - "for" — импортные автомобили (fc_carsearchlist.do?carType=for)
          - "kor" — отечественные автомобили (dc_carsearchlist.do?carType=kor)
        В API это соответствует CarType.N (for) и CarType.Y (kor) в параметре q.
        """
        headers = {
            'Origin': 'https://www.encar.com',
            'Referer': 'https://www.encar.com/',
        }
        car_type_flag = 'N' if car_type == 'for' else 'Y'
        params = {
            'count': 'true',
            'q': f'(And.Hidden.N._.CarType.{car_type_flag}.)',
            'sr': f"|ModifiedDate|{offset}|{limit}"
        }
        try:
            resp = self._session_get(self.list_url, params=params, headers=headers, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.warning(
                    "event=encar_list_fetch_failed status=%s car_type=%s offset=%s limit=%s body=%s",
                    resp.status_code, car_type, offset, limit, (resp.text or "")[:200]
                )
                return None
        except Exception as e:
            logger.exception(
                "event=encar_list_fetch_exception car_type=%s offset=%s limit=%s err=%s",
                car_type, offset, limit, e
            )
            return None

    def fetch_vehicle_detail(self, car_id: str) -> Optional[Dict]:
        headers = {
            'Origin': 'https://fem.encar.com',
            'Referer': 'https://fem.encar.com/',
        }
        include = "ADVERTISEMENT,CATEGORY,CONDITION,CONTACT,MANAGE,OPTIONS,PHOTOS,SPEC,PARTNERSHIP,CENTER,VIEW"
        url = f"{self.vehicle_detail_url.format(car_id)}?include={include}"
        try:
            resp = self._session_get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.warning("event=encar_detail_fetch_failed car_id=%s status=%s", car_id, resp.status_code)
                return None
        except Exception as e:
            logger.exception("event=encar_detail_fetch_exception car_id=%s err=%s", car_id, e)
            return None

    def fetch_record(self, car_id: str, plate_number: str) -> Optional[Dict]:
        if not plate_number:
            return None
        headers = {
            'Origin': 'https://fem.encar.com',
            'Referer': 'https://fem.encar.com/',
        }
        url = self.record_url.format(car_id)
        try:
            resp = self._session_get(url, params={"vehicleNo": plate_number}, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.info("event=encar_record_fetch_non200 car_id=%s status=%s", car_id, resp.status_code)
                return None
        except Exception as e:
            logger.exception("event=encar_record_fetch_exception car_id=%s err=%s", car_id, e)
            return None

    def fetch_diagnosis(self, car_id: str) -> Optional[Dict]:
        headers = {
            'Origin': 'https://fem.encar.com',
            'Referer': 'https://fem.encar.com/',
        }
        url = self.diagnosis_url.format(car_id)
        try:
            resp = self._session_get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                logger.debug("event=encar_diagnosis_fetch_ok car_id=%s", car_id)
                return resp.json()
            else:
                logger.info("event=encar_diagnosis_fetch_non200 car_id=%s status=%s", car_id, resp.status_code)
                return None
        except Exception as e:
            logger.exception("event=encar_diagnosis_fetch_exception car_id=%s err=%s", car_id, e)
            return None

    # ---------- Новый метод для получения полной инспекции ----------
    def fetch_inspection(self, car_id: str) -> Optional[Dict]:
        """Получает полные данные инспекции (техническое состояние + кузов)."""
        headers = {
            'Origin': 'https://fem.encar.com',
            'Referer': 'https://fem.encar.com/',
        }
        url = self.inspection_url.format(car_id)
        try:
            resp = self._session_get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                logger.debug("event=encar_inspection_fetch_ok car_id=%s", car_id)
                return resp.json()
            else:
                logger.info("event=encar_inspection_fetch_non200 car_id=%s status=%s", car_id, resp.status_code)
                return None
        except Exception as e:
            logger.exception("event=encar_inspection_fetch_exception car_id=%s err=%s", car_id, e)
            return None

    def fetch_sellingpoint(self, car_id: str) -> Optional[Dict]:
        headers = {
            'Origin': 'https://fem.encar.com',
            'Referer': 'https://fem.encar.com/',
        }
        url = self.sellingpoint_url.format(car_id)
        try:
            resp = self._session_get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            else:
                return None
        except Exception:
            return None

    def fetch_user(self, seller_id: str) -> Optional[Dict]:
        if not seller_id:
            return None
        headers = {
            'Origin': 'https://fem.encar.com',
            'Referer': 'https://fem.encar.com/',
        }
        url = self.user_url.format(seller_id)
        try:
            resp = self._session_get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            else:
                return None
        except Exception:
            return None

    # ================== МЕТОД parse_inspection ==================
    def parse_inspection(self, inspection: dict, diagnosis: dict = None) -> dict:
        """
        Парсит данные инспекции (техническое состояние) и диагностики кузова.
        Возвращает структурированный словарь для фронта.
        """
        result = {
            'basicInfo': {},
            'engineTransmission': {},
            'chassis': {},
            'electrical': {},
            'interior': {},
            'bodyChanged': {},
            'additional': {},
            'bodyPanels': [],
            'bodyComments': '',
        }

        # ------------------ Инспекция (техническое состояние) ------------------
        if inspection and isinstance(inspection, dict):
            master = inspection.get('master', {})
            if not isinstance(master, dict):
                master = {}
            detail = master.get('detail', {})
            if not isinstance(detail, dict):
                detail = {}

            # Базовая информация
            result['basicInfo'] = {
                'VIN': detail.get('vin', ''),
                'Пробег': detail.get('mileage', ''),
                'Дата инспекции': detail.get('issueDate', ''),
                'Инспектор': detail.get('inspName', ''),
                'Организация': detail.get('noticeName', ''),
                'Комментарии инспекции': detail.get('comments', ''),
                'Состояние двигателя': 'OK' if detail.get('engineCheck') == 'Y' else '',
                'Состояние трансмиссии': 'OK' if detail.get('trnsCheck') == 'Y' else '',
                'Следы воды': 'Есть' if detail.get('waterlog') else 'Нет',
                'Отзыв производителя': 'Есть' if detail.get('recall') else 'Нет',
                'Пробег подтверждён': (detail.get('mileageStateType') or {}).get('title', ''),
            }

            # Парсинг дерева inners (техническое состояние)
            engine_transmission = {}
            chassis = {}
            electrical = {}

            def walk(items, parent=None):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    t = item.get('type') or {}
                    if not isinstance(t, dict):
                        t = {}
                    name = t.get('title')
                    status_type = item.get('statusType') or {}
                    if not isinstance(status_type, dict):
                        status_type = {}
                    status = status_type.get('title')
                    children = item.get('children', [])
                    if not isinstance(children, list):
                        children = []

                    # Определяем группу
                    group = parent if parent is not None else name

                    if group:
                        key = name or group
                        if '엔진' in group or '원동기' in group:
                            engine_transmission[key] = status
                        elif '변속' in group or '동력' in group:
                            engine_transmission[key] = status
                        elif '조향' in group or '제동' in group or '현가' in group:
                            chassis[key] = status
                        elif '전기' in group or '계기' in group or '전장' in group:
                            electrical[key] = status

                    if children:
                        walk(children, group)

            inners = inspection.get('inners', [])
            if not isinstance(inners, list):
                inners = []
            walk(inners)
            result['engineTransmission'] = engine_transmission
            result['chassis'] = chassis
            result['electrical'] = electrical

            # Парсинг outers (состояние кузова и салона)
            body_changed = {}
            interior = {}

            # Корейские названия деталей кузова → русские (как на Encar)
            outer_part_ru = {
                '프론트 펜더 왼쪽': 'Левое переднее крыло',
                '프론트 펜더 오른쪽': 'Правое переднее крыло',
                '리어 펜더 왼쪽': 'Левое заднее крыло',
                '리어 펜더 오른쪽': 'Правое заднее крыло',
                '후드': 'Капот',
                '트렁크 리드': 'Крышка багажника',
                '프론트 도어 왼쪽': 'Левая передняя дверь',
                '프론트 도어 오른쪽': 'Правая передняя дверь',
                '리어 도어 왼쪽': 'Левая задняя дверь',
                '리어 도어 오른쪽': 'Правая задняя дверь',
                '프론트 도어': 'Передняя дверь',
                '리어 도어': 'Задняя дверь',
                '펜더': 'Крыло',
                '도어': 'Дверь',
            }
            inner_part_ru = {
                '운전석 시트': 'Водительское сиденье', '시트(좌)': 'Водительское сиденье', '앞좌석(좌)': 'Водительское сиденье',
                '조수석 시트': 'Пассажирское сиденье', '시트(우)': 'Пассажирское сиденье', '앞좌석(우)': 'Пассажирское сиденье',
                '후석': 'Заднее сиденье', '뒷좌석': 'Заднее сиденье',
                '스티어링 휠': 'Руль', '핸들': 'Руль',
                '대시보드': 'Панель приборов', '계기판': 'Панель приборов',
                '실링': 'Потолок', '천장': 'Потолок',
                '센터페시아': 'Центральная консоль', '콘솔': 'Центральная консоль',
                '내장(좌)': 'Передняя дверь (левая) - внутри', '도어(좌)': 'Передняя дверь (левая) - внутри',
                '내장(우)': 'Передняя дверь (правая) - внутри', '도어(우)': 'Передняя дверь (правая) - внутри',
            }
            # Корейский статус → русский
            status_ru = {
                '교체': 'замена',
                '도장': 'покрашено',
                '판금': 'ремонт',
                '수리': 'ремонт',
                '교환': 'замена',
                '도색': 'покрашено',
                '리폼': 'ремонт',
                '부품교체': 'замена',
                '정상': 'оригинал',
            }

            outers = inspection.get('outers', [])
            if not isinstance(outers, list):
                outers = []
            for part in outers:
                if not isinstance(part, dict):
                    continue
                part_name = str(part.get('title') or part.get('partName') or part.get('name') or part.get('part') or '').strip()
                status_type = part.get('statusType') or {}
                if not isinstance(status_type, dict):
                    status_type = {}
                status = str(status_type.get('title') or status_type.get('name') or part.get('status') or part.get('result') or '').strip()
                if not part_name:
                    continue

                # Нормализуем название детали для bodyChanged (русский, если есть маппинг)
                part_name_ru = outer_part_ru.get(part_name, part_name)
                status_ru_val = status_ru.get(status, status)

                # Для bodyChanged – замена/покраска: русские, английские и корейские маркеры
                status_lower = (status or '').lower()
                status_raw = (status or '')
                is_replacement = (
                    any(k in status_lower for k in ['заменено', 'покрашено', 'замена', 'painted', 'replaced']) or
                    any(k in status_raw for k in ['교체', '도장', '판금', '수리', '교환', '도색', '리폼', '부품교체'])
                )
                if is_replacement:
                    body_changed[part_name_ru] = status_ru_val

                # Для interior – элементы салона по ключевым словам; маппинг на русские названия зон схемы
                low = part_name.lower()
                if ('시트' in part_name or '내장' in part_name or '트림' in part_name or
                    'interior' in low or 'салон' in low or 'seat' in low or 'сиденье' in low):
                    interior[part_name] = status
                    part_interior_ru = inner_part_ru.get(part_name, part_name)
                    if is_replacement and part_interior_ru != part_name:
                        body_changed[part_interior_ru] = status_ru_val

            result['bodyChanged'] = body_changed
            result['interior'] = interior

            # Дополнительные блоки
            additional = {}
            if master.get('accident') is not None:
                additional['ДТП'] = master.get('accident')
            if master.get('simpleRepair') is not None:
                additional['Косметический ремонт'] = master.get('simpleRepair')
            if detail.get('waterlog'):
                additional['Следы воды'] = detail.get('waterlog')
            if detail.get('recall'):
                additional['Отзыв производителя'] = detail.get('recall')
            result['additional'] = additional

        # ------------------ Диагностика кузова ------------------
        if diagnosis and isinstance(diagnosis, dict):
            items = diagnosis.get('items', [])
            if not isinstance(items, list):
                items = []

            # Маппинг английских названий панелей на русские (как на Encar)
            panel_mapping = {
                # Внешние элементы (детальные)
                'FRONT_DOOR_LEFT': 'Левая передняя дверь',
                'FRONT_DOOR_RIGHT': 'Правая передняя дверь',
                'BACK_DOOR_LEFT': 'Левая задняя дверь',
                'BACK_DOOR_RIGHT': 'Правая задняя дверь',
                'HOOD': 'Капот',
                'TRUNK_LID': 'Крышка багажника',
                'FRONT_FENDER_LEFT': 'Левое переднее крыло',
                'FRONT_FENDER_RIGHT': 'Правое переднее крыло',
                'REAR_FENDER_LEFT': 'Левое заднее крыло',
                'REAR_FENDER_RIGHT': 'Правое заднее крыло',
                'BACK_FENDER_LEFT': 'Левое заднее крыло',
                'BACK_FENDER_RIGHT': 'Правое заднее крыло',
                # Внешние элементы (групповые, как в diagnosis report)
                'FRONT_FENDER': 'Передние крылья',
                'FRONT_DOOR': 'Передние двери',
                'BACK_DOOR': 'Задние двери',
                # Внутренние/силовые элементы (frame diagnostic items)
                'FRONT_PANEL_INSIDE_PANEL': 'Передняя панель / внутренняя панель',
                'FRONT_WHEEL_HOUSING_REAR_WHEEL_HOUSING': 'Арки колес (перед/зад)',
                'PILLAR_PANEL_DASH_PANEL_FLOOR_PANEL': 'Стойки / щиток / пол',
                'SIDE_SILL_PANEL_QUARTER_PANEL': 'Пороги / четверти кузова',
                'REAR_PANEL_TRUNK_FLOOR': 'Задняя панель / пол багажника',
                'SIDE_MEMBER_LOOP_PANEL_PACKAGE_TRAY': 'Лонжероны / полка багажника',
            }
            status_mapping = {
                'NORMAL': 'оригинал',
                'REPLACEMENT': 'замена',
                'PAINT': 'покрашено',
                'REPAIR': 'ремонт',
            }
            # Текст результата с корейского
            result_text_ru = {
                '정상': 'оригинал',
                '교체': 'замена',
                '원장': 'оригинал',
                '도장': 'покрашено',
                '판금': 'ремонт',
                '수리': 'ремонт',
            }

            body_panels = []
            checker_comment = ''
            outer_panel_comment = ''

            for item in items:
                if not isinstance(item, dict):
                    continue
                name = item.get('name')
                if name in panel_mapping:
                    result_code = item.get('resultCode') or item.get('resultCodeType')
                    result_raw = (item.get('result') or '').strip()
                    if result_code:
                        status = status_mapping.get(result_code, result_code)
                    elif result_raw:
                        status = result_text_ru.get(result_raw, result_raw)
                    else:
                        status = 'оригинал'
                    body_panels.append({
                        'part': panel_mapping[name],
                        'status': status,
                        'section': 'internal' if name in {
                            'FRONT_PANEL_INSIDE_PANEL',
                            'FRONT_WHEEL_HOUSING_REAR_WHEEL_HOUSING',
                            'PILLAR_PANEL_DASH_PANEL_FLOOR_PANEL',
                            'SIDE_SILL_PANEL_QUARTER_PANEL',
                            'REAR_PANEL_TRUNK_FLOOR',
                            'SIDE_MEMBER_LOOP_PANEL_PACKAGE_TRAY',
                        } else 'external',
                    })
                elif name == 'CHECKER_COMMENT':
                    checker_comment = item.get('result', '')
                elif name == 'OUTER_PANEL_COMMENT':
                    outer_panel_comment = item.get('result', '')

            result['bodyPanels'] = body_panels

            # Если в диагностике есть замены — дополняем bodyChanged (чтобы блок «Заменённые детали» не был пустым)
            for p in body_panels:
                st = str(p.get('status') or '').strip().lower()
                if st in ('замена', 'покрашено', 'ремонт') and p.get('part'):
                    if p['part'] not in result['bodyChanged']:
                        result['bodyChanged'][p['part']] = st

            # Сбор всех комментариев
            comments_parts = []
            if result['basicInfo'].get('Комментарии инспекции'):
                comments_parts.append(result['basicInfo']['Комментарии инспекции'])
            if checker_comment:
                comments_parts.append(checker_comment)
            if outer_panel_comment:
                comments_parts.append(outer_panel_comment)
            result['bodyComments'] = "\n\n".join(comments_parts)

        return result
    # ================== КОНЕЦ МЕТОДА ==================

    # ---------- Нормализация данных ----------
    def normalize_car(self, car_id: str, item: Dict, detail: Optional[Dict],
                      photos: List[Dict], diagnosis: Optional[Dict],
                      inspection: Optional[Dict], sellingpoint: Optional[Dict],
                      record: Optional[Dict], user_info: Optional[Dict],
                      inspection_structured: Optional[Dict] = None) -> Dict:
        """
        Преобразует сырые данные в структуру, аналогичную выдаче конкурента.
        """
        now = datetime.now().isoformat() + "+03:00"

        # --- Из item (поисковая выдача) ---
        manufacturer = self._as_text(item.get('Manufacturer', ''))
        model = self._as_text(item.get('Model', ''))
        badge = self._as_text(item.get('Badge', ''))
        year = self._as_text(item.get('Year', ''))
        month = str(item.get('Month', '')).zfill(2) if item.get('Month') else ''
        price_won = self._as_int(item.get('Price')) or 0
        price = str(price_won // 10000) if price_won else ''
        monthly_finance_price = self._is_monthly_finance_listing(item)
        if monthly_finance_price:
            price_won = 0
            price = ''
        km_age = str(item.get('Mileage', ''))
        # Объём двигателя (см³): из списка (displacement/Displacement) или из detail.spec
        displacement_raw = item.get('displacement') or item.get('Displacement')
        if displacement_raw is not None and displacement_raw != '':
            displacement = str(int(displacement_raw)) if isinstance(displacement_raw, (int, float)) else str(displacement_raw).strip()
        else:
            displacement = ''
        if not displacement and detail:
            spec = detail.get('spec', {}) or {}
            if not isinstance(spec, dict):
                spec = {}
            displacement = str(spec.get('engineDisplacement') or spec.get('displacement') or spec.get('Displacement') or '')
        description = self._as_text(item.get('Description', ''))

        # --- Из detail (детальная информация) ---
        vin = self._as_text(detail.get('vin', '') if detail else '')
        vehicleNo = self._as_text(detail.get('vehicleNo', '') if detail else '')
        spec = detail.get('spec', {}) if detail else {}
        category = detail.get('category', {}) if detail else {}
        grade_name = self._as_text(category.get('gradeName', '') if category else '')
        contact = detail.get('contact', {}) if detail else {}
        manage = detail.get('manage', {}) if detail else {}
        advertisement = detail.get('advertisement', {}) if detail else {}
        if not isinstance(spec, dict):
            spec = {}
        if not isinstance(category, dict):
            category = {}
        if not isinstance(contact, dict):
            contact = {}
        if not isinstance(manage, dict):
            manage = {}
        if not isinstance(advertisement, dict):
            advertisement = {}

        # Характеристики из spec
        color = self._as_text(spec.get('colorName', ''))
        engine_type = self._as_text(spec.get('fuelName', ''))
        transmission_type = self._as_text(spec.get('transmissionName', ''))
        body_type = self._as_text(spec.get('bodyName', ''))
        seat_count = self._as_text(spec.get('seatCount', ''))

        # Мощность (л.с.): 1) encar (item.hp), 2) lookup car_power_lookup.json, 3) парсим из badge/gradeName, 4) engine_map.json
        power = ''
        power_from_engine_map = False
        lookup = self._get_power_lookup()

        # 1. Из ответа encar (редко, но бывает)
        hp_item = item.get('hp') or item.get('power')
        if hp_item is not None and str(hp_item).strip():
            power = self._normalize_power_to_hp(hp_item)
            if power:
                key = f"{manufacturer}|{model}|{badge}".strip()
                if key and "|" in key:
                    try:
                        lookup[key] = int(power) if power.isdigit() else power
                        self._save_lookup(lookup)
                        logger.info("Мощность из encar сохранена в lookup: %s -> %s л.с.", key, power)
                    except Exception as e:
                        logger.debug("Не удалось сохранить в lookup: %s", e)

        # 2. Поиск в lookup-файле (от самой точной комбинации к общей)
        if not power:
            key_variants = [
                f"{manufacturer}|{model}|{badge}".strip(),
                f"{manufacturer}|{model}|{grade_name}".strip(),
                f"{manufacturer}|{model}".strip(),
                f"{manufacturer}|{badge}".strip(),
            ]
            for key in key_variants:
                if not key or "|" not in key:
                    continue
                if key in lookup:
                    val = lookup[key]
                    power = self._normalize_power_to_hp(val)
                    if power and 20 <= int(power) <= 2000:
                        logger.info("Мощность из lookup: %s -> %s л.с.", key, power)
                        break

        # 3. Парсим из строк (бейдж/комплектация)
        if not power:
            power = self._extract_power_from_string(badge) or self._extract_power_from_string(grade_name) or ''
            if power and not (20 <= int(power) <= 2000):
                power = ''

        # 4. Каталог двигателей engine_map.json (марка/модель/объём/топливо/турбо)
        if not power:
            try:
                from engine_hp_resolver import resolve_engine_hp

                cat = (detail.get("category") or {}) if detail else {}
                if not isinstance(cat, dict):
                    cat = {}
                hint = {
                    "mark": self._as_text(cat.get("manufacturerName") or manufacturer),
                    "manufacturerName": self._as_text(cat.get("manufacturerName") or manufacturer),
                    "model": self._as_text(cat.get("modelName") or model),
                    "modelName": self._as_text(cat.get("modelName") or model),
                    "modelGroupName": self._as_text(cat.get("modelGroupName") or ""),
                    "generation": self._as_text(badge),
                    "configuration": self._as_text(badge),
                    "gradeName": self._as_text(grade_name),
                    "displacement": self._as_text(displacement),
                    "engine_type": self._as_text(engine_type),
                    "year": self._as_text(year),
                }
                hp_int = resolve_engine_hp(hint, record_source=False)
                if hp_int is not None:
                    power = str(hp_int)
                    power_from_engine_map = True
            except ImportError:
                pass

        # 5. Если не найдено — пустая строка (на фронте прочерк)
        if power:
            self._power_stats["with_power"] += 1
        else:
            self._power_stats["without_power"] += 1

        # Адрес продавца
        address = self._as_text(contact.get('address', ''))

        # Данные о продавце
        separation = item.get('Separation')
        if isinstance(separation, list):
            seller_id = separation[0] if separation else None
        else:
            seller_id = None
        seller = user_info.get('userId') if user_info else seller_id
        salon_id = self._as_text(contact.get('no', ''))
        seller_type = 'DEALER' if contact.get('userType') == 'DEALER' else 'CLIENT'
        is_dealer = seller_type == 'DEALER'

        # Даты
        offer_created = manage.get('firstAdvertisedDateTime', now)

        # Статус объявления
        advertisement_type = advertisement.get('advertisementType', 'NORMAL')
        sales_status = advertisement.get('salesStatus', '')

        # Корейские названия
        manufacturer_name = self._as_text(category.get('manufacturerName', ''))
        model_name = self._as_text(category.get('modelName', ''))
        grade_name = grade_name or self._as_text(category.get('gradeName', ''))
        model_group_name = self._as_text(category.get('modelGroupName', ''))

        # Опции – просто список кодов
        options = detail.get('options', {}) if detail else {}
        standard_options = options.get('standard', [])
        if not isinstance(standard_options, list):
            standard_options = []

        # Тип привода: 1) прямое поле из списка API (DriveType/driveType), 2) spec.driveType из деталей, 3) разбор badge
        drive_from_item = item.get('DriveType') or item.get('driveType')
        drive_from_spec = (spec.get('driveType') or spec.get('DriveType')) if spec else None
        drive_type = (
            self._normalize_drive_type_from_api(drive_from_item)
            or self._normalize_drive_type_from_api(drive_from_spec)
            or self._extract_drive_type(badge)
        )
        if not drive_type and (drive_from_item or drive_from_spec):
            logger.debug(
                "drive_type не определён: car_id=%s item.DriveType=%s spec.driveType=%s badge=%s",
                car_id, drive_from_item, drive_from_spec, str(badge or '')[:80]
            )
        is_awd = (drive_type == 'AWD')
        prep_drive_type = drive_type  # обратная совместимость с фильтром и карточками

        # --- Диагностика и фото ---
        diag_photos = []
        car_photos = []
        h_images = []

        advertisement = detail.get("advertisement", {}) if detail else {}
        if not isinstance(advertisement, dict):
            advertisement = {}

        # underBodyPhotos
        if advertisement.get("hasUnderBodyPhoto"):
            under_body_photos = advertisement.get("underBodyPhotos", [])
            if not isinstance(under_body_photos, list):
                under_body_photos = []
            for p in under_body_photos:
                if not isinstance(p, dict):
                    continue
                url = p.get("photoUrl")
                if url:
                    diag_photos.append(url)

        # используем ПЕРЕДАННЫЕ photos или фото из detail
        photo_source = []
        if isinstance(photos, list) and photos:
            photo_source = photos
        else:
            maybe_detail_photos = detail.get("photos", []) if detail else []
            if isinstance(maybe_detail_photos, list):
                photo_source = maybe_detail_photos

        for p in photo_source:
            if not isinstance(p, dict):
                continue
            photo_type = p.get("type")
            path = p.get("path")

            if photo_type == "DIAG2":
                if path:
                    diag_photos.append("http://imgcar.encar.com" + path)
                continue

            # Основные фото через ci.encar.com
            url = self.build_carphoto_url(p, now)
            if url:
                car_photos.append(url)

            # Добавляем в h_images
            h_images.append({
                'code': p.get('code', ''),
                'desc': p.get('desc'),
                'path': path,
                'type': photo_type,
                'updateDateTime': p.get('updateDateTime', now)
            })

        # --- Осмотр ---
        inspection_data = detail.get("condition", {}).get("inspection", {}) if detail else {}
        inspection_formats = inspection_data.get("formats") or []
        damage_summary = self._extract_damage_summary(record, diagnosis, inspection_structured)
        source_shapes = self._source_shapes(item, detail, diagnosis, inspection, sellingpoint, record, user_info)
        required_contract = {
            "inner_id": car_id,
            "url": f"http://www.encar.com/dc/dc_cardetailview.do?carid={car_id}",
            "mark": manufacturer,
            "model": model,
            "year": year,
        }
        missing_required_fields = [k for k, v in required_contract.items() if v in ("", None)]

        # --- Сборка data ---
        data = {
            'id': '',
            'inner_id': car_id,
            'url': f"http://www.encar.com/dc/dc_cardetailview.do?carid={car_id}",
            'mark': manufacturer,
            'model': model,
            'generation': badge,
            'configuration': badge,
            'complectation': '',
            'year': year,
            'color': color,
            'price': price,
            'price_won': price_won,
            'encar_monthly_finance_price': monthly_finance_price,
            'encar_month_lease_price': item.get('MonthLeasePrice'),
            'encar_month_lease_rent_price': item.get('MonthLeaseRentPrice'),
            'encar_month_lease_rest': item.get('MonthLeaseRest'),
            'encar_lease_type': item.get('LeaseType'),
            'encar_attribute_type': item.get('AttributeType'),
            'encar_price_type': item.get('PriceType'),
            'encar_price_type_name': item.get('PriceTypeName'),
            'price_text': item.get('PriceView') or item.get('PriceText'),
            'km_age': km_age,
            'engine_type': engine_type,
            'transmission_type': transmission_type,
            'body_type': body_type,
            'address': address,
            'seller_type': seller_type,
            'is_dealer': is_dealer,
            'section': 'б/у',
            'seller': seller,
            'salon_id': salon_id,
            'description': description,
            'displacement': displacement,
            'offer_created': offer_created,
            'manufacturerName': manufacturer_name,
            'modelName': model_name,
            'gradeName': grade_name,
            'modelGroupName': model_group_name,
            'yearMonth': year + month,
            'images': json.dumps(car_photos, ensure_ascii=False),
            'h_images': json.dumps(h_images, ensure_ascii=False),
            'advertisementType': advertisement_type,
            'salesStatus': sales_status,
            'created_at': now,
            'power': power,
            'power_kwh': '',
            'power_kwhp': '',
            'power_otherp': '',
            'extra': {
                'diagnosis': diagnosis,
                'diagnosis_photos': diag_photos,
                'inspection': inspection,
                'inspection_structured': inspection_structured,
                'inspection_formats': inspection_formats,
                'sellingpoint': sellingpoint,
                'record_open': record,
            },
            'options': {'standard': standard_options},
            'is_duplicate': False,
            'prep_drive_type': prep_drive_type,
            'drive_type': drive_type,
            'is_awd': is_awd,
            'vin': vin,
            'seatColor': '',
            'seatCount': str(seat_count) if seat_count else '',
            'parser_schema_version': PARSER_SCHEMA_VERSION,
            'parser_normalized_at': now,
            'data_quality': {
                'detail_present': bool(detail),
                'diagnosis_present': bool(diagnosis),
                'inspection_present': bool(inspection),
                'record_present': bool(record),
                'sellingpoint_present': bool(sellingpoint),
                'user_present': bool(user_info),
                'missing_required_fields': missing_required_fields,
            },
            'parser_source_shapes': source_shapes["keys"],
            'parser_source_shapes_hash': source_shapes["hashes"],
            **damage_summary,
        }

        if power_from_engine_map:
            data["power_source"] = "engine_map"
            data["power_estimated"] = True

        intent, signals = classify_encar_price_intent(data)
        data["price_intent"] = intent
        data["price_intent_confidence"] = "high" if signals else "low"
        data["price_signals"] = price_signals_json(signals)
        data["price_classifier_version"] = "v1"
        if intent in ("monthly_finance", "reserved_placeholder"):
            data["price_on_request"] = True
            data["encar_listing_reserved"] = True if intent == "reserved_placeholder" else data.get("encar_listing_reserved", False)
            data.pop("my_price", None)

        clean = build_catalog_clean_layers(data)
        data.update(clean)

        quality_reasons = []
        if missing_required_fields:
            quality_reasons.append("missing_required_fields")
        for endpoint in ("detail", "diagnosis", "inspection", "record", "sellingpoint", "user"):
            if not data["data_quality"].get(f"{endpoint}_present"):
                quality_reasons.append(f"{endpoint}_missing")
        if intent == "monthly_finance":
            quality_reasons.append("price_intent_monthly_finance")
        elif intent == "reserved_placeholder":
            quality_reasons.append("price_intent_reserved_placeholder")
        data["data_quality"]["reasons"] = quality_reasons
        contract_violations = validate_raw_json_min_contract(data)
        data["data_quality"]["contract_violations"] = contract_violations
        if contract_violations:
            quality_reasons.append("raw_json_min_contract_violation")

        if not data.get("inner_id") or not data.get("url") or not data.get("source", "encar"):
            logger.warning("parser contract warning: missing core id/url fields for car_id=%s", car_id)
        data.setdefault("source", "encar")

        return {
            'id': 0,
            'inner_id': car_id,
            'change_type': 'added',
            'created_at': now,
            'data': data
        }

    # ---------- Сбор данных ----------
    def collect_cars(self, max_cars_per_type: int = 20, delay: float = 0.5,
                     car_types: tuple = ("for",)) -> List[Dict]:
        """
        Собирает данные по указанным типам автомобилей.

        max_cars_per_type — максимум машин для каждого типа (for/kor).
        car_types — кортеж источников: "for" (импорт), "kor" (отечественные).
        """
        all_cars = []
        limit = 50
        car_counter = 0

        logger.info("event=encar_collect_start car_types=%s max_cars_per_type=%s delay=%s", car_types, max_cars_per_type, delay)

        for car_type in car_types:
            collected_for_type = 0
            offset = 0
            type_label = "импортные" if car_type == "for" else "отечественные"

            logger.info("event=encar_collect_type_start car_type=%s type_label=%s", car_type, type_label)

            while collected_for_type < max_cars_per_type:
                logger.info(
                    "event=encar_collect_list_page car_type=%s offset=%s collected_for_type=%s max_cars_per_type=%s total_collected=%s",
                    car_type, offset, collected_for_type, max_cars_per_type, len(all_cars)
                )
                list_data = self.fetch_list_page(offset, limit, car_type=car_type)
                if not list_data:
                    logger.warning("event=encar_collect_list_missing car_type=%s offset=%s", car_type, offset)
                    break

                items = list_data.get('SearchResults', [])
                if not items:
                    logger.info("event=encar_collect_list_empty car_type=%s offset=%s", car_type, offset)
                    break

                logger.info("event=encar_collect_list_items car_type=%s offset=%s items=%s", car_type, offset, len(items))

                for idx, item in enumerate(items, 1):
                    if collected_for_type >= max_cars_per_type:
                        break

                    car_id = item['Id']
                    seller_id = item.get('Separation', [None])[0] if item.get('Separation') else None

                    logger.info(
                        "event=encar_collect_car_start car_id=%s type_label=%s index=%s max_per_type=%s manufacturer=%s model=%s badge=%s",
                        car_id, type_label, collected_for_type + 1, max_cars_per_type,
                        item.get("Manufacturer"), item.get("Model"), item.get("Badge")
                    )

                    # 1. Детальные данные
                    logger.debug("event=encar_collect_phase car_id=%s phase=detail", car_id)
                    detail = self.fetch_vehicle_detail(car_id)
                    plate_number = detail.get('vehicleNo') if detail else None

                    # 2. Диагностика (всегда запрашиваем — для блока «Диагностика кузова» и заменённых панелей)
                    diagnosis = None
                    logger.debug("event=encar_collect_phase car_id=%s phase=diagnosis", car_id)
                    diagnosis = self.fetch_diagnosis(car_id)

                    # 3. История
                    record = None
                    if plate_number:
                        logger.debug("event=encar_collect_phase car_id=%s phase=record", car_id)
                        record = self.fetch_record(car_id, plate_number)

                    # 4. Особенности и продавец
                    logger.debug("event=encar_collect_phase car_id=%s phase=seller", car_id)
                    sellingpoint = self.fetch_sellingpoint(car_id)
                    user_info = self.fetch_user(seller_id) if seller_id else None

                    # 5. Полная инспекция (через отдельный API)
                    logger.debug("event=encar_collect_phase car_id=%s phase=inspection", car_id)
                    full_inspection = self.fetch_inspection(car_id)
                    # Если не получилось, пробуем взять из detail (на случай, если API вернёт ошибку)
                    if not full_inspection and detail:
                        full_inspection = detail.get("condition", {}).get("inspection")

                    # ===== ВЫЗОВ МЕТОДА parse_inspection =====
                    inspection_structured = self.parse_inspection(full_inspection, diagnosis)

                    # --- Нормализация ---
                    normalized = self.normalize_car(
                        car_id, item, detail, None, diagnosis,
                        full_inspection, sellingpoint, record, user_info,
                        inspection_structured=inspection_structured
                    )
                    car_counter += 1
                    normalized['id'] = car_counter
                    normalized['data']['id'] = str(car_counter)

                    all_cars.append(normalized)
                    collected_for_type += 1
                    logger.info("event=encar_collect_car_added car_id=%s type_label=%s total=%s", car_id, type_label, len(all_cars))

                    time.sleep(delay)

                offset += limit

        logger.info("event=encar_collect_done total=%s", len(all_cars))
        return all_cars

    def save_to_file(self, cars: List[Dict], filename: str = 'cars.json'):
        output = {
            'result': cars,
            'meta': {
                'page': 1,
                'next_page': 2,
                'limit': len(cars)
            }
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        # Статистика
        total_photos = sum(len(json.loads(car['data']['images'])) for car in cars if car['data'].get('images'))
        cars_with_diagnosis = sum(1 for car in cars if car['data']['extra'].get('diagnosis_photos'))
        cars_with_inspection = sum(1 for car in cars if car['data']['extra'].get('inspection_formats'))

        logger.info(
            "event=encar_save_file_done filename=%s cars=%s total_photos=%s with_diagnosis=%s with_inspection=%s",
            filename, len(cars), total_photos, cars_with_diagnosis, cars_with_inspection
        )

if __name__ == '__main__':
    parser = EncarFullParser()
    # Собираем как импортные, так и отечественные автомобили.
    # max_cars_per_type=40 означает до 40 машин для каждого типа.
    cars = parser.collect_cars(max_cars_per_type=40, delay=0.3, car_types=("for", "kor"))
    parser.save_to_file(cars, str((Path(__file__).resolve().parent.parent / "web" / "public" / "cars.json")))