import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Как купить авто из Кореи",
  description:
    "Пошаговый импорт из Южной Кореи: этапы сделки, калькулятор растаможки и ориентир по стоимости под ключ.",
  alternates: { canonical: "/buy" },
};

export default function BuyPage() {
  return (
    <iframe
      title="Как купить авто из Кореи — World Ride Auto"
      src="/howtobuy.html"
      className="block h-dvh w-full border-0"
    />
  );
}
