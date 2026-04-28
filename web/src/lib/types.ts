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
};

export type SlimCar = {
  id: string;
  inner_id?: string | number | null;
  title?: string;
  price?: number | null;
  /** Из data.price_on_request или эвристика «нет my_price». */
  price_on_request?: boolean;
  /** cars.created_at (ISO) — бейдж «добавлено сегодня», сортировка в Meili. */
  catalog_created_at?: string | null;
  /** Дневной чекер Encar: объявление снято с продажи до ночной выгрузки. */
  encar_listing_sold?: boolean;
  /** Дневной чекер Dongchedi: объявление снято с продажи до ночной выгрузки. */
  dongchedi_listing_sold?: boolean;
  year_num?: number;
  data?: {
    images?: string[];
    year?: string | number;
    mark?: string;
    model?: string;
    [key: string]: unknown;
  };
};

export type SearchResponse = {
  result: SlimCar[];
  meta: SearchMeta;
};

export type CarDetailResponse = {
  result: Record<string, unknown>;
};

export type SimilarMeta = {
  car_id: string;
  limit: number;
  total_candidates: number;
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
  models: FacetRow[];
  generations: FacetRow[];
  trims: FacetRow[];
  bodies: FacetRow[];
  fuels: FacetRow[];
  transmissions: FacetRow[];
  colors: FacetRow[];
};
