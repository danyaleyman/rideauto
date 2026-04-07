/* Легаси-страница: те же <link>, что в frontend/car.html. */
/* eslint-disable @next/next/no-css-tags -- статика из sync-legacy-assets */
/* eslint-disable @next/next/no-page-custom-font -- Roboto как на car.html */
import type { ReactNode } from "react";
import { CarBodyClass } from "@/components/legacy-car/CarBodyClass";

export default function CarLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link
        rel="preconnect"
        href="https://fonts.gstatic.com"
        crossOrigin="anonymous"
      />
      <link rel="preconnect" href="https://ci.encar.com" crossOrigin="anonymous" />
      <link rel="dns-prefetch" href="https://ci.encar.com" />
      <link rel="dns-prefetch" href="https://cdnjs.cloudflare.com" />
      <link
        rel="stylesheet"
        href="https://fonts.googleapis.com/css2?family=Roboto:ital,wght@0,400;0,500;0,600;0,700;1,400&display=optional"
      />
      <link rel="stylesheet" href="/css/common.css" />
      <link rel="stylesheet" href="/css/cookie-consent.css" />
      <link rel="stylesheet" href="/css/auth-favorites.css" />
      <link rel="stylesheet" href="/css/car-tailwind.css?v=20260403tw" />
      <link rel="stylesheet" href="/css/car-page-inline.css" />
      <link
        rel="stylesheet"
        href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"
        crossOrigin="anonymous"
      />
      <CarBodyClass />
      {children}
    </>
  );
}
