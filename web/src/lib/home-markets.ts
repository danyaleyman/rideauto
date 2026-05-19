import { HOME_LANDING_MEDIA, type MediaCascade } from "@/lib/home-landing-media";

export type HomeMarketId = "korea" | "china" | "japan";

export type HomeMarket = {
  id: HomeMarketId;
  country: string;
  modelLabel: string;
  media: MediaCascade;
  catalogHref: string;
  catalogDisabled?: boolean;
  catalogLabel?: string;
  points: string[];
};

export const HOME_MARKETS: HomeMarket[] = [
  {
    id: "korea",
    country: "Корея",
    modelLabel: "Hyundai Kona N Line",
    media: HOME_LANDING_MEDIA.markets.korea,
    catalogHref: "/catalog?region=korea",
    points: [
      "Свежие комплектации и понятная история обслуживания",
      "Площадки Encar и аукционы — широкий выбор под бюджет",
      "Быстрый отбор по пробегу, комплектации и отчётам осмотра",
    ],
  },
  {
    id: "china",
    country: "Китай",
    modelLabel: "Xiaomi YU7",
    media: HOME_LANDING_MEDIA.markets.china,
    catalogHref: "/catalog?region=china",
    points: [
      "Новые модели и богатые комплектации по цене",
      "Проверка истории и состояния до выкупа",
      "Прозрачная смета: выкуп, логистика и таможня",
    ],
  },
  {
    id: "japan",
    country: "Япония",
    modelLabel: "Toyota Land Cruiser 250",
    media: HOME_LANDING_MEDIA.markets.japan,
    catalogHref: "/catalog?region=japan",
    catalogDisabled: true,
    catalogLabel: "Каталог в разработке",
    points: [
      "Аукционы USS, TAA, ARAI — доступ к редким лотам",
      "Аккуратные пробеги и сильная ликвидность моделей",
      "Диагностика и видеоосмотр до принятия решения",
    ],
  },
];
