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
