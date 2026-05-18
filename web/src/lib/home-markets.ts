export type HomeMarketId = "korea" | "china" | "japan";

export type HomeMarket = {
  id: HomeMarketId;
  country: string;
  modelLabel: string;
  modelUrl: string;
  catalogHref: string;
  points: string[];
};

export const HOME_MARKETS: HomeMarket[] = [
  {
    id: "korea",
    country: "Корея",
    modelLabel: "Hyundai Kona N Line",
    modelUrl: "/assets/2025_hyundai_kona_n_line.glb",
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
    modelUrl: "/assets/2025_xiaomi_yu7.glb",
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
    modelUrl: "/assets/2024_toyota_land_cruiser_250_first_edition.glb",
    catalogHref: "/catalog?region=japan",
    points: [
      "Аукционы USS, TAA, ARAI — доступ к редким лотам",
      "Аккуратные пробеги и сильная ликвидность моделей",
      "Диагностика и видеоосмотр до принятия решения",
    ],
  },
];
