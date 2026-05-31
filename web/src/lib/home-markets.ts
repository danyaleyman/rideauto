import { HOME_LANDING_MEDIA, type MediaCascade } from "@/lib/home-landing-media";

export type HomeMarketId = "korea" | "china" | "japan";

export type HomeMarket = {
  id: HomeMarketId;
  modelLabel: string;
  media: MediaCascade;
  catalogHref: string;
  catalogDisabled?: boolean;
};

export const HOME_MARKETS: HomeMarket[] = [
  {
    id: "korea",
    modelLabel: "Hyundai Kona N Line",
    media: HOME_LANDING_MEDIA.markets.korea,
    catalogHref: "/catalog?region=korea",
  },
  {
    id: "china",
    modelLabel: "Xiaomi YU7",
    media: HOME_LANDING_MEDIA.markets.china,
    catalogHref: "/catalog?region=china",
  },
  {
    id: "japan",
    modelLabel: "Toyota Land Cruiser 250",
    media: HOME_LANDING_MEDIA.markets.japan,
    catalogHref: "/catalog?region=japan",
    catalogDisabled: true,
  },
];
