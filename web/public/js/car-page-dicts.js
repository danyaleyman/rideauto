(function () {
  'use strict';
  // ---------- СЛОВАРИ ДЛЯ ПЕРЕВОДА ----------
  const partNamesRu = {
      // Детали кузова (outers), если придут с API без маппинга в парсере
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
      '실린더 커버(로커암 커버)': 'Клапанная крышка',
      '실린더 헤드 / 개스킷': 'ГБЦ / прокладка',
      '실린더 블록 / 오일팬': 'Блок цилиндров / поддон',
      '오일 유량': 'Уровень масла',
      '워터펌프': 'Помпа',
      '라디에이터': 'Радиатор',
      '냉각수 수량': 'Уровень ОЖ',
      '클러치 어셈블리': 'Сцепление в сборе',
      '등속조인트': 'ШРУС',
      '추친축 및 베어링': 'Кардан / подшипники',
      '디피렌셜 기어': 'Дифференциал',
      '동력조향 작동 오일 누유': 'Течь масла ГУР',
      '스티어링 펌프': 'Насос ГУР',
      '스티어링 기어(MDPS포함)': 'Рулевая рейка',
      '스티어링 조인트': 'Рулевой шарнир',
      '파워고압호스': 'Шланг ГУР',
      '타이로드엔드 및 볼 조인트': 'Наконечники / шаровые',
      '브레이크 마스터 실린더오일 누유': 'Течь ГТЦ',
      '브레이크 오일 누유': 'Течь тормозной жидкости',
      '배력장치 상태': 'Вакуумный усилитель',
      '발전기 출력': 'Генератор',
      '시동 모터': 'Стартер',
      '와이퍼 모터 기능': 'Мотор стеклоочистителя',
      '실내송풍 모터': 'Печка',
      '라디에이터 팬 모터': 'Вентилятор радиатора',
      '윈도우 모터': 'Стеклоподъёмник',
  };
  const statusRu = {
      '없음': 'Отсутствует',
      '양호': 'Нормально',
      '적정': 'В норме',
      '불량': 'Неисправно',
      '미세누유': 'Микротечь',
      '누유': 'Течь',
      '미세누수': 'Микротечь (вода)',
      '누수': 'Течь (вода)',
      '과다': 'Избыток',
      '부족': 'Недостаток',
      '정상': 'Норма',
      '있음': 'Присутствует',
      '교체': 'замена',
      '도장': 'покрашено',
      '판금': 'ремонт',
      '수리': 'ремонт',
      '교환': 'замена',
      '도색': 'покрашено',
      '리폼': 'ремонт',
      '부품교체': 'замена',
      '원장': 'оригинал',
  };
  // Перевод на русский: тип кузова, топливо, коробка, цвет (без корейских символов в выводе)
  const displayRu = {
      'AWD': 'Полный привод', '2WD': '2WD', 'FWD': 'Передний привод', 'RWD': 'Задний привод',
      '가솔린': 'Бензин', '디젤': 'Дизель', 'LPG': 'Газ', 'LPG/가솔린': 'Газ/бензин', '하이브리드': 'Гибрид', '전기': 'Электро', '가솔린+전기': 'Гибрид', '수소': 'Водород', '디젤+전기': 'Дизель гибрид',
      'Gasoline': 'Бензин', 'Diesel': 'Дизель', 'Electric': 'Электро', 'Hybrid': 'Гибрид', 'Hydrogen': 'Водород', 'LPG/Gasoline': 'Газ/бензин', 'Diesel Hybrid': 'Дизель гибрид',
      '세단': 'Седан', 'SUV': 'Внедорожник', '해치백': 'Хэтчбек', '왜건': 'Универсал', '쿠페': 'Купе', '픽업': 'Пикап', '밴': 'Фургон', '중형차': 'Седан среднего класса', '대형차': 'Седан полноразмерный', '소형차': 'Компакт', '경차': 'Микролитражный', '미니밴': 'Минивэн', 'RV': 'Внедорожник', '스포츠카': 'Спорткар', '승합차': 'Микроавтобус', '화물차': 'Грузовой автомобиль',
      'Sedan': 'Седан', 'Hatchback': 'Хэтчбек', 'Wagon': 'Универсал', 'Coupe': 'Купе', 'Pickup': 'Пикап', 'Van': 'Фургон', 'Midsize': 'Седан среднего класса', 'Full-size': 'Седан полноразмерный', 'Compact': 'Компакт', 'Minivan': 'Минивэн', 'Light car': 'Микролитражный', 'Sports car': 'Спорткар', 'Minibus': 'Микроавтобус', 'Commercial vehicle': 'Грузовой автомобиль',
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
  
  // Маппинг корейский → английский (марка, модель, поколение, тип, комплектация); дополняется из data/encar_mapping.json
  const filterMappingKoEn = {
      mark: { '현대': 'Hyundai', '기아': 'Kia', '제네시스': 'Genesis', '쌍용': 'SsangYong', '한국GM': 'GM Korea', '르노코리아': 'Renault Korea', '벤츠': 'Mercedes-Benz', 'BMW': 'BMW', '아우디': 'Audi', '폭스바겐': 'Volkswagen', '포르쉐': 'Porsche', '미니': 'MINI', '볼보': 'Volvo', '렉서스': 'Lexus', '토요타': 'Toyota', '혼다': 'Honda', '닛산': 'Nissan', '인피니티': 'Infiniti', '마쓰다': 'Mazda', '미쓰비시': 'Mitsubishi', '스바루': 'Subaru', '스즈키': 'Suzuki', '다이하쓰': 'Daihatsu', '포드': 'Ford', '쉐보레': 'Chevrolet', '지프': 'Jeep', '캐딜락': 'Cadillac', '테슬라': 'Tesla', '폴스타': 'Polestar', '랜드로버': 'Land Rover', '재규어': 'Jaguar', '벤틀리': 'Bentley', '롤스로이스': 'Rolls-Royce', '마세라티': 'Maserati', '페라리': 'Ferrari', '람보르기니': 'Lamborghini', '알파로메오': 'Alfa Romeo', '피아트': 'Fiat' },
      model: {}, generation: {}, type: {}, trim: {}
  };
  function toDisplayEn(val, category) {
      if (!val) return val;
      const s = String(val).trim();
      const map = category && filterMappingKoEn[category] ? filterMappingKoEn[category] : null;
      if (!map) return val;
      if (map && map[s]) return map[s];
      const key = Object.keys(map).find(k => String(k).trim() === s);
      if (key) return map[key];
      const sLower = s.toLowerCase();
      const keyLower = Object.keys(map).find(k => String(k).trim().toLowerCase() === sLower);
      if (keyLower) return map[keyLower];
      return val;
  }
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
  function filterOptionLabel(val, category) {
      const s = String(val || '').trim();
      const ruCategories = ['bodyType', 'engineType', 'transmission', 'color'];
      if (ruCategories.indexOf(category) >= 0) {
          const en = toDisplayEn(s, category);
          return sanitizeUiLabel(toDisplayRu(en || s) || en || s);
      }
      let en = toDisplayEn(s, category);
      if (en !== s) return sanitizeUiLabel(en);
      if (['model', 'generation', 'type', 'trim'].indexOf(category) >= 0) {
          const fallback = applyKoreanPhraseFallback(s);
          if (fallback !== s) {
              return sanitizeUiLabel(fallback || s);
          }
      }
      return sanitizeUiLabel(toDisplayRu(s) || s);
  }
  fetch('/data/encar_mapping.json').then(r => r.ok ? r.json() : null).catch(() => null).then(m => {
      if (m && typeof m === 'object') {
          ['mark','model','generation','type','trim'].forEach(cat => {
              if (m[cat] && typeof m[cat] === 'object') {
                  filterMappingKoEn[cat] = Object.assign({}, filterMappingKoEn[cat] || {}, m[cat]);
              }
          });
      }
  });
  
  // ---------- Маппинг опций ----------
  const optionRu = {
      '010': 'Люк',
      '001': 'Светодиодные фары',
      '029': 'Ксеноновые фары',
      '075': 'Светодиодные фары',
      '059': 'Электропривод багажника',
      '080': 'Доводчик дверей',
      '024': 'Электрозеркала',
      '017': 'Легкосплавные диски',
      '062': 'Рейлинги',
      '082': 'Подогрев руля',
      '083': 'Электрорегулировка руля',
      '084': 'Подрулевые лепестки',
      '031': 'Кнопки на руле',
      '030': 'Автозатемнение зеркала',
      '074': 'Транспондер (Hi‑Pass)',
      '006': 'Центральный замок',
      '008': 'Усилитель руля',
      '007': 'Электростеклоподъёмники',
      '002': 'Подушки безопасности',
      '026': 'Подушка водителя',
      '027': 'Подушка пассажира',
      '020': 'Боковые подушки',
      '056': 'Шторки безопасности',
      '019': 'Противобуксовочная',
      '055': 'Курсовая устойчивость',
      '033': 'Датчик давления в шинах',
      '088': 'Система удержания полосы',
      '085': 'Парктроник передний',
      '032': 'Парктроник задний',
      '086': 'Система слепых зон',
      '058': 'Камера заднего вида',
      '087': 'Камера 360°',
      '003': 'Парктроник',
      '068': 'Круиз-контроль',
      '079': 'Адаптивный круиз',
      '095': 'Проекционный дисплей',
      '094': 'Электронный ручник',
      '023': 'Климат-контроль',
      '057': 'Бесключевой доступ',
      '015': 'ДУ замками',
      '081': 'Датчик дождя',
      '097': 'Автосвет',
      '092': 'Шторки задних сидений',
      '093': 'Электрошторка',
      '005': 'Навигация',
      '004': 'Головное устройство',
      '054': 'Развлечения для задних',
      '096': 'Bluetooth',
      '072': 'USB',
      '071': 'AUX',
      '014': 'Кожаный салон',
      '021': 'Электропривод водителя',
      '035': 'Электропривод пассажира',
      '089': 'Электропривод задних',
      '022': 'Подогрев передних',
      '063': 'Подогрев задних',
      '051': 'Память водителя',
      '078': 'Память пассажира',
      '034': 'Вентиляция водителя',
      '077': 'Вентиляция пассажира',
      '090': 'Вентиляция задних',
      '091': 'Массаж',
  };
  const categoryRu = {
      '01': 'Экстерьер и салон',
      '02': 'Безопасность',
      '03': 'Комфорт и мультимедиа',
      '04': 'Сиденья',
  };
  
  // ---------- Данные об опциях из Encar ----------
  const optionMaster = {
      "metas": [
          { "key": "01", "value": "외관/내장" },
          { "key": "02", "value": "안전" },
          { "key": "03", "value": "편의/멀티미디어" },
          { "key": "04", "value": "시트" }
      ],
      "options": [
          { "optionCd": "010", "optionName": "선루프", "optionTypeCd": "01" },
          { "optionCd": "001", "optionName": "헤드램프", "optionTypeCd": "01" },
          { "optionCd": "029", "optionName": "헤드램프(HID)", "optionTypeCd": "01" },
          { "optionCd": "075", "optionName": "헤드램프(LED)", "optionTypeCd": "01" },
          { "optionCd": "059", "optionName": "파워 전동 트렁크", "optionTypeCd": "01" },
          { "optionCd": "080", "optionName": "고스트 도어 클로징", "optionTypeCd": "01" },
          { "optionCd": "024", "optionName": "전동접이 사이드 미러", "optionTypeCd": "01" },
          { "optionCd": "017", "optionName": "알루미늄 휠", "optionTypeCd": "01" },
          { "optionCd": "062", "optionName": "루프랙", "optionTypeCd": "01" },
          { "optionCd": "082", "optionName": "열선 스티어링 휠", "optionTypeCd": "01" },
          { "optionCd": "083", "optionName": "전동 조절 스티어링 휠", "optionTypeCd": "01" },
          { "optionCd": "084", "optionName": "패들 시프트", "optionTypeCd": "01" },
          { "optionCd": "031", "optionName": "스티어링 휠 리모컨", "optionTypeCd": "01" },
          { "optionCd": "030", "optionName": "ECM 룸미러", "optionTypeCd": "01" },
          { "optionCd": "074", "optionName": "하이패스", "optionTypeCd": "01" },
          { "optionCd": "006", "optionName": "파워 도어록", "optionTypeCd": "01" },
          { "optionCd": "008", "optionName": "파워 스티어링 휠", "optionTypeCd": "01" },
          { "optionCd": "007", "optionName": "파워 윈도우", "optionTypeCd": "01" },
          { "optionCd": "002", "optionName": "에어백", "optionTypeCd": "02" },
          { "optionCd": "026", "optionName": "에어백(운전석)", "optionTypeCd": "02" },
          { "optionCd": "027", "optionName": "에어백(동승석)", "optionTypeCd": "02" },
          { "optionCd": "020", "optionName": "에어백(사이드)", "optionTypeCd": "02" },
          { "optionCd": "056", "optionName": "에어백(커튼)", "optionTypeCd": "02" },
          { "optionCd": "019", "optionName": "미끄럼 방지(TCS)", "optionTypeCd": "02" },
          { "optionCd": "055", "optionName": "차체자세 제어장치(ESC)", "optionTypeCd": "02" },
          { "optionCd": "033", "optionName": "타이어 공기압센서(TPMS)", "optionTypeCd": "02" },
          { "optionCd": "088", "optionName": "차선이탈 경보 시스템(LDWS)", "optionTypeCd": "02" },
          { "optionCd": "085", "optionName": "주차감지센서(전방)", "optionTypeCd": "02" },
          { "optionCd": "032", "optionName": "주차감지센서(후방)", "optionTypeCd": "02" },
          { "optionCd": "086", "optionName": "후측방 경보 시스템", "optionTypeCd": "02" },
          { "optionCd": "058", "optionName": "후방 카메라", "optionTypeCd": "02" },
          { "optionCd": "087", "optionName": "360도 어라운드 뷰", "optionTypeCd": "02" },
          { "optionCd": "068", "optionName": "크루즈 컨트롤(일반)", "optionTypeCd": "03" },
          { "optionCd": "079", "optionName": "크루즈 컨트롤(어댑티브)", "optionTypeCd": "03" },
          { "optionCd": "095", "optionName": "헤드업 디스플레이(HUD)", "optionTypeCd": "03" },
          { "optionCd": "094", "optionName": "전자식 주차브레이크(EPB)", "optionTypeCd": "03" },
          { "optionCd": "023", "optionName": "자동 에어컨", "optionTypeCd": "03" },
          { "optionCd": "057", "optionName": "스마트키", "optionTypeCd": "03" },
          { "optionCd": "015", "optionName": "무선도어 잠금장치", "optionTypeCd": "03" },
          { "optionCd": "081", "optionName": "레인센서", "optionTypeCd": "03" },
          { "optionCd": "097", "optionName": "오토 라이트", "optionTypeCd": "03" },
          { "optionCd": "092", "optionName": "커튼/블라인드(뒷좌석)", "optionTypeCd": "03" },
          { "optionCd": "093", "optionName": "커튼/블라인드(후방)", "optionTypeCd": "03" },
          { "optionCd": "005", "optionName": "내비게이션", "optionTypeCd": "03" },
          { "optionCd": "004", "optionName": "앞좌석 AV 모니터", "optionTypeCd": "03" },
          { "optionCd": "054", "optionName": "뒷좌석 AV 모니터", "optionTypeCd": "03" },
          { "optionCd": "096", "optionName": "블루투스", "optionTypeCd": "03" },
          { "optionCd": "072", "optionName": "USB 단자", "optionTypeCd": "03" },
          { "optionCd": "071", "optionName": "AUX 단자", "optionTypeCd": "03" },
          { "optionCd": "014", "optionName": "가죽시트", "optionTypeCd": "04" },
          { "optionCd": "021", "optionName": "전동시트(운전석)", "optionTypeCd": "04" },
          { "optionCd": "035", "optionName": "전동시트(동승석)", "optionTypeCd": "04" },
          { "optionCd": "089", "optionName": "전동시트(뒷좌석)", "optionTypeCd": "04" },
          { "optionCd": "022", "optionName": "열선시트(앞좌석)", "optionTypeCd": "04" },
          { "optionCd": "063", "optionName": "열선시트(뒷좌석)", "optionTypeCd": "04" },
          { "optionCd": "051", "optionName": "메모리 시트(운전석)", "optionTypeCd": "04" },
          { "optionCd": "078", "optionName": "메모리 시트(동승석)", "optionTypeCd": "04" },
          { "optionCd": "034", "optionName": "통풍시트(운전석)", "optionTypeCd": "04" },
          { "optionCd": "077", "optionName": "통풍시트(동승석)", "optionTypeCd": "04" },
          { "optionCd": "090", "optionName": "통풍시트(뒷좌석)", "optionTypeCd": "04" },
          { "optionCd": "091", "optionName": "마사지 시트", "optionTypeCd": "04" }
      ]
  };
  
  const optionTypeMap = {};
  optionMaster.options.forEach(opt => { optionTypeMap[opt.optionCd] = opt.optionTypeCd; });
  
  function groupOptionsRu(optionCodes) {
      const groups = {};
      optionCodes.forEach(code => {
          const typeCd = optionTypeMap[code] || 'другое';
          const catName = categoryRu[typeCd] || 'Другое';
          const optName = optionRu[code] || code;
          if (!groups[catName]) groups[catName] = [];
          groups[catName].push(optName);
      });
      return groups;
  }
  
  function renderOptionsGrouped(optionCodes) {
      if (!optionCodes || optionCodes.length === 0) return '';
      const groups = groupOptionsRu(optionCodes);
      const orderedCategories = ['Экстерьер и салон', 'Безопасность', 'Комфорт и мультимедиа', 'Сиденья', 'Другое'];
      var optionsTooltip = 'В комплектацию входят стандартные опции, которые указал продавец.<br><br>Для получения точного списка опций, необходима выгрузка по VIN-номеру';
      let html = '<div class="card options-equipment-block">';
      html += '<h2 class="options-block-title has-tooltip">Опции и оборудование<span class="tooltip-popup">' + optionsTooltip + '</span></h2>';
      orderedCategories.forEach((cat, catIndex) => {
          if (groups[cat] && groups[cat].length > 0) {
              const count = groups[cat].length;
              const isFirst = catIndex === 0;
              html += `<div class="option-accordion-item${isFirst ? ' is-open' : ''}">`;
              html += `<button type="button" class="option-accordion-header" data-options-index="${catIndex}" aria-expanded="${isFirst}" aria-controls="options-body-${catIndex}" id="options-header-${catIndex}">`;
              html += `<span class="option-category-name">${cat}</span>`;
              html += '<span class="option-accordion-meta"><span class="option-count">' + count + '</span><span class="option-accordion-icon" aria-hidden="true"><svg class="option-accordion-svg" viewBox="0 0 24 24" width="20" height="20" fill="none" xmlns="http://www.w3.org/2000/svg"><path class="opt-acc-chev" d="M7 10l5 5 5-5" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"/><path class="opt-acc-check" d="M6.5 12.5l4 4 9-9" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"/></svg></span></span>';
              html += `</button>`;
              html += `<div class="option-accordion-body" id="options-body-${catIndex}" role="region" aria-labelledby="options-header-${catIndex}">`;
              html += '<div class="option-tags">';
              groups[cat].forEach(optName => {
                  html += `<span class="badge-option">${optName}</span>`;
              });
              html += '</div></div></div>';
          }
      });
      html += '</div>';
      return html;
  }

    window.WRA_CAR_PAGE_DICTS = {
        partNamesRu: partNamesRu,
        statusRu: statusRu,
        displayRu: displayRu,
        toDisplayRu: toDisplayRu,
        filterMappingKoEn: filterMappingKoEn,
        toDisplayEn: toDisplayEn,
        koreanPhraseToEn: koreanPhraseToEn,
        applyKoreanPhraseFallback: applyKoreanPhraseFallback,
        containsHangul: containsHangul,
        stripKoreanForTitlePart: stripKoreanForTitlePart,
        sanitizeUiLabel: sanitizeUiLabel,
        filterOptionLabel: filterOptionLabel,
        optionRu: optionRu,
        categoryRu: categoryRu,
        optionMaster: optionMaster,
        optionTypeMap: optionTypeMap,
        groupOptionsRu: groupOptionsRu,
        renderOptionsGrouped: renderOptionsGrouped
    };
})();
