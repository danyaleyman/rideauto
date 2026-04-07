import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Script from "next/script";
import WebVitalsReporter from "@/components/WebVitalsReporter";
import { getSiteUrl } from "@/lib/env";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL(`${getSiteUrl()}/`),
  title: {
    default: "World Ride Auto — авто из Азии",
    template: "%s — World Ride Auto",
  },
  description:
    "Автомобили из Кореи и Азии с доставкой во Владивосток. Каталог, фильтры, цены и оформление через World Ride Auto.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <head>
        <link rel="stylesheet" href="/css/cookie-consent.css?v=20260410" />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <Script
          src="/js/wra-site-config.js?v=20260421"
          strategy="beforeInteractive"
        />
        <Script
          src="/js/cookie-consent.js?v=20260421"
          strategy="afterInteractive"
        />
        <WebVitalsReporter />
        {children}
      </body>
    </html>
  );
}
