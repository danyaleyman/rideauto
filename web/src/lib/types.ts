export type SearchMeta = {
  total: number;
  limit: number;
  per_page: number;
  pages: number;
  offset: number;
  next_cursor?: string | null;
  next_page?: number | null;
  processing_time_ms?: number | null;
  list_mode?: string;
  sort?: string | null;
  /** Зеркало `WRA_API_CONTRACT_VERSION` на бэкенде (`v1` / `v2`). */
  api_version?: string;
};

export type SlimCar = {
  id: string;
  inner_id?: string | number | null;
  title?: string;
  price?: number | null;
  /** Слой цены корейского контура: полный расчёт / Корея+логистика / по запросу. */
  pricing_tier?: "full_customs" | "korea_land_only" | "price_on_request" | string;
  /** True, если в оценке учтена таможня РФ (``full_customs``). */
  customs_included?: boolean;
  /** Из data.price_on_request или эвристика «нет my_price». */
  price_on_request?: boolean;
  /** cars.created_at (ISO) — бейдж «добавлено сегодня», сортировка в Meili. */
  catalog_created_at?: string | null;
  /** cars.updated_at (ISO) — свежесть строки; на API v2 обязателен. */
  catalog_updated_at?: string | null;
  /** Дневной чекер корейского контура: объявление снято с продажи до ночной выгрузки. */
  encar_listing_sold?: boolean;
  /** Маркер «резерв / черновая цена» в корейском контуре (не финальная цена продажи). */
  encar_listing_reserved?: boolean;
  /** Дневной чекер китайского контура: объявление снято с продажи до ночной выгрузки. */
  dongchedi_listing_sold?: boolean;
  year_num?: number;
  data?: {
    images?: string[];
    year?: string | number;
    mark?: string;
    model?: string;
    /** VIN для склейки дублей одного авто под разными id объявления. */
    vin?: string;
    [key: string]: unknown;
  };
};

export type SearchResponse = {
  result: SlimCar[];
  meta: SearchMeta;
};

export type CarDetailResponse = {
  result: Record<string, unknown>;
  api_version?: string;
};

export type SimilarMeta = {
  car_id: string;
  limit: number;
  total_candidates: number;
  api_version?: string;
};

export type SimilarResponse = {
  result: SlimCar[];
  meta: SimilarMeta;
};

export type CatalogDailyAdditionsResponse = {
  count: number;
  region: string;
  local_date: string;
  timezone: string;
};

export type AuthUser = {
  id: number;
  email: string;
  is_active: boolean;
  last_login_at?: string | null;
};

export type AuthMeResponse = {
  authenticated: boolean;
  user: AuthUser | null;
};

export type AuthSimpleOk = {
  ok: boolean;
};

export type FacetRow = {
  value: string;
  label?: string;
  values?: string[];
  count: number;
};

export type FacetsResponse = {
  marks: FacetRow[];
  clusters: FacetRow[];
  models: FacetRow[];
  generations: FacetRow[];
  trims: FacetRow[];
  bodies: FacetRow[];
  fuels: FacetRow[];
  transmissions: FacetRow[];
  colors: FacetRow[];
  api_version?: string;
};
