import requests
import json
import time
import urllib.parse
import re
from urllib.parse import urlencode
from typing import List, Dict, Optional
from datetime import datetime

class EncarFullParser:
    def __init__(self):
        self.session = requests.Session()
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
    def _extract_drive_type(self, badge: str) -> str:
        if not badge:
            return ''
        badge_upper = badge.upper()
        awd_keywords = ['AWD', '4WD', '4X4', '4×4', 'XDRIVE', '4MATIC', 'ALL4', 'QUATTRO']
        for kw in awd_keywords:
            if kw in badge_upper:
                return 'AWD'
        rwd_keywords = ['RWD', 'REAR']
        for kw in rwd_keywords:
            if kw in badge_upper:
                return 'RWD'
        fwd_keywords = ['FWD', 'FRONT']
        for kw in fwd_keywords:
            if kw in badge_upper:
                return 'FWD'
        return ''

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
            resp = self.session.get(self.list_url, params=params, headers=headers, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"Ошибка списка {resp.status_code}: {resp.text[:200]}")
                return None
        except Exception as e:
            print(f"Исключение при загрузке списка: {e}")
            return None

    def fetch_vehicle_detail(self, car_id: str) -> Optional[Dict]:
        headers = {
            'Origin': 'https://fem.encar.com',
            'Referer': 'https://fem.encar.com/',
        }
        include = "ADVERTISEMENT,CATEGORY,CONDITION,CONTACT,MANAGE,OPTIONS,PHOTOS,SPEC,PARTNERSHIP,CENTER,VIEW"
        url = f"{self.vehicle_detail_url.format(car_id)}?include={include}"
        try:
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"  Детальные данные {resp.status_code} для {car_id}")
                return None
        except Exception as e:
            print(f"  Ошибка детальных данных {car_id}: {e}")
            return None

    def fetch_record(self, car_id: str, plate_number: str) -> Optional[Dict]:
        if not plate_number:
            return None
        headers = {
            'Origin': 'https://fem.encar.com',
            'Referer': 'https://fem.encar.com/',
        }
        encoded_plate = urllib.parse.quote(plate_number)
        url = self.record_url.format(car_id) + f"?vehicleNo={encoded_plate}"
        try:
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"    📑 История {resp.status_code} для {car_id}")
                return None
        except Exception as e:
            print(f"  Ошибка истории {car_id}: {e}")
            return None

    def fetch_diagnosis(self, car_id: str) -> Optional[Dict]:
        headers = {
            'Origin': 'https://fem.encar.com',
            'Referer': 'https://fem.encar.com/',
        }
        url = self.diagnosis_url.format(car_id)
        try:
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                print(f"    ✅ Диагностика получена для {car_id}")
                return resp.json()
            else:
                print(f"    📑 Диагностика {resp.status_code} для {car_id}")
                return None
        except Exception as e:
            print(f"    📝 Ошибка диагностики {car_id}: {e}")
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
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                print(f"    ✅ Полная инспекция получена для {car_id}")
                return resp.json()
            else:
                print(f"    📑 Полная инспекция {resp.status_code} для {car_id}")
                return None
        except Exception as e:
            print(f"    📝 Ошибка полной инспекции {car_id}: {e}")
            return None

    def fetch_sellingpoint(self, car_id: str) -> Optional[Dict]:
        headers = {
            'Origin': 'https://fem.encar.com',
            'Referer': 'https://fem.encar.com/',
        }
        url = self.sellingpoint_url.format(car_id)
        try:
            resp = self.session.get(url, headers=headers, timeout=10)
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
            resp = self.session.get(url, headers=headers, timeout=10)
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
            detail = master.get('detail', {})

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
                    t = item.get('type') or {}
                    name = t.get('title')
                    status = (item.get('statusType') or {}).get('title')
                    children = item.get('children', [])

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

            walk(inspection.get('inners', []))
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

            for part in inspection.get('outers', []):
                part_name = (part.get('title') or part.get('partName') or part.get('name') or part.get('part') or '').strip()
                status_type = part.get('statusType') or {}
                status = (status_type.get('title') or status_type.get('name') or part.get('status') or part.get('result') or '').strip()
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

                # Для interior – элементы салона по ключевым словам
                low = part_name.lower()
                if ('시트' in part_name or '내장' in part_name or '트림' in part_name or
                    'interior' in low or 'салон' in low or 'seat' in low or 'сиденье' in low):
                    interior[part_name] = status

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

            # Маппинг английских названий панелей на русские (как на Encar)
            panel_mapping = {
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
            }
            status_mapping = {
                'NORMAL': 'оригинал',
                'REPLACEMENT': 'замена',
            }
            # Текст результата с корейского
            result_text_ru = {'정상': 'оригинал', '교체': 'замена', '원장': 'оригинал'}

            body_panels = []
            checker_comment = ''
            outer_panel_comment = ''

            for item in items:
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
                        'status': status
                    })
                elif name == 'CHECKER_COMMENT':
                    checker_comment = item.get('result', '')
                elif name == 'OUTER_PANEL_COMMENT':
                    outer_panel_comment = item.get('result', '')

            result['bodyPanels'] = body_panels

            # Если в диагностике есть замены — дополняем bodyChanged (чтобы блок «Заменённые детали» не был пустым)
            for p in body_panels:
                if p.get('status') == 'замена' and p.get('part'):
                    if p['part'] not in result['bodyChanged']:
                        result['bodyChanged'][p['part']] = 'замена'

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
        manufacturer = item.get('Manufacturer', '')
        model = item.get('Model', '')
        badge = item.get('Badge', '')
        year = str(item.get('Year', ''))
        month = str(item.get('Month', '')).zfill(2) if item.get('Month') else ''
        price_won = int(item.get('Price', 0))
        price = str(price_won // 10000) if price_won else ''
        km_age = str(item.get('Mileage', ''))
        displacement = str(item.get('Displacement', ''))
        description = item.get('Description', '')

        # --- Из detail (детальная информация) ---
        vin = detail.get('vin', '') if detail else ''
        vehicleNo = detail.get('vehicleNo', '') if detail else ''
        spec = detail.get('spec', {}) if detail else {}
        category = detail.get('category', {}) if detail else {}
        contact = detail.get('contact', {}) if detail else {}
        manage = detail.get('manage', {}) if detail else {}
        advertisement = detail.get('advertisement', {}) if detail else {}

        # Характеристики из spec
        color = spec.get('colorName', '')
        engine_type = spec.get('fuelName', '')
        transmission_type = spec.get('transmissionName', '')
        body_type = spec.get('bodyName', '')
        seat_count = spec.get('seatCount', '')

        # Мощность – пробуем из inspection, если есть
        power = ''
        if inspection and 'master' in inspection:
            master = inspection.get('master', {})
            detail_insp = master.get('detail', {})
            power = str(detail_insp.get('hcout', ''))

        # Адрес продавца
        address = contact.get('address', '')

        # Данные о продавце
        seller_id = item.get('Separation', [None])[0] if item.get('Separation') else None
        seller = user_info.get('userId') if user_info else seller_id
        salon_id = contact.get('no', '')
        seller_type = 'DEALER' if contact.get('userType') == 'DEALER' else 'CLIENT'
        is_dealer = seller_type == 'DEALER'

        # Даты
        offer_created = manage.get('firstAdvertisedDateTime', now)

        # Статус объявления
        advertisement_type = advertisement.get('advertisementType', 'NORMAL')
        sales_status = advertisement.get('salesStatus', '')

        # Корейские названия
        manufacturer_name = category.get('manufacturerName', '')
        model_name = category.get('modelName', '')
        grade_name = category.get('gradeName', '')
        model_group_name = category.get('modelGroupName', '')

        # Опции – просто список кодов
        options = detail.get('options', {}) if detail else {}
        standard_options = options.get('standard', [])

        # Тип привода из badge
        prep_drive_type = self._extract_drive_type(badge)

        # --- Диагностика и фото ---
        diag_photos = []
        car_photos = []
        h_images = []

        advertisement = detail.get("advertisement", {}) if detail else {}

        # underBodyPhotos
        if advertisement.get("hasUnderBodyPhoto"):
            for p in advertisement.get("underBodyPhotos", []):
                url = p.get("photoUrl")
                if url:
                    diag_photos.append(url)

        # используем ПЕРЕДАННЫЕ photos или фото из detail
        photo_source = photos if photos else (detail.get("photos", []) if detail else [])

        for p in photo_source:
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
            'vin': vin,
            'seatColor': '',
            'seatCount': str(seat_count) if seat_count else ''
        }

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

        print("=" * 60)
        print("Начинаем сбор данных с encar.com...")
        print("=" * 60)

        for car_type in car_types:
            collected_for_type = 0
            offset = 0
            type_label = "импортные" if car_type == "for" else "отечественные"

            print(f"\n--- Начинаем сбор для типа: {type_label} ({car_type}) ---")

            while collected_for_type < max_cars_per_type:
                print(f"\n📋 [{type_label}] Загрузка списка offset={offset} "
                      f"(собрано для типа: {collected_for_type}/{max_cars_per_type}, всего: {len(all_cars)})...")
                list_data = self.fetch_list_page(offset, limit, car_type=car_type)
                if not list_data:
                    print("❌ Не удалось загрузить список")
                    break

                items = list_data.get('SearchResults', [])
                if not items:
                    print("❌ Нет автомобилей в списке")
                    break

                print(f"📦 Получено {len(items)} автомобилей в текущей странице")

                for idx, item in enumerate(items, 1):
                    if collected_for_type >= max_cars_per_type:
                        break

                    car_id = item['Id']
                    seller_id = item.get('Separation', [None])[0] if item.get('Separation') else None

                    print(f"\n  🔍 [{collected_for_type + 1}/{max_cars_per_type} для {type_label}] Обработка {car_id}...")
                    print(f"  📌 {item.get('Manufacturer')} {item.get('Model')} - {item.get('Badge')}")

                    # 1. Детальные данные
                    print(f"    ⏳ Запрос детальных данных...")
                    detail = self.fetch_vehicle_detail(car_id)
                    plate_number = detail.get('vehicleNo') if detail else None

                    # 2. Диагностика (всегда запрашиваем — для блока «Диагностика кузова» и заменённых панелей)
                    diagnosis = None
                    print(f"    ⏳ Запрос диагностики...")
                    diagnosis = self.fetch_diagnosis(car_id)

                    # 3. История
                    record = None
                    if plate_number:
                        print(f"    ⏳ Запрос истории...")
                        record = self.fetch_record(car_id, plate_number)

                    # 4. Особенности и продавец
                    print(f"    ⏳ Запрос информации о продавце...")
                    sellingpoint = self.fetch_sellingpoint(car_id)
                    user_info = self.fetch_user(seller_id) if seller_id else None

                    # 5. Полная инспекция (через отдельный API)
                    print(f"    ⏳ Запрос полной инспекции...")
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
                    print(f"  ✅ Автомобиль {car_id} ({type_label}) успешно добавлен")

                    time.sleep(delay)

                offset += limit

        print("\n" + "=" * 60)
        print(f"🎉 Сбор завершён! Получено {len(all_cars)} автомобилей.")
        print("=" * 60)
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

        print(f"\n📊 Статистика сохранения:")
        print(f"   - Файл: {filename}")
        print(f"   - Автомобилей: {len(cars)}")
        print(f"   - Всего фотографий: {total_photos}")
        print(f"   - С диагностикой: {cars_with_diagnosis}")
        print(f"   - С осмотром: {cars_with_inspection}")
        print(f"✅ Данные сохранены!")

if __name__ == '__main__':
    parser = EncarFullParser()
    # Собираем как импортные, так и отечественные автомобили.
    # max_cars_per_type=40 означает до 40 машин для каждого типа.
    cars = parser.collect_cars(max_cars_per_type=40, delay=0.3, car_types=("for", "kor"))
    parser.save_to_file(cars, 'cars.json')