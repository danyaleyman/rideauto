import type { Metadata } from "next";
import { Geist_Mono, Inter } from "next/font/google";
import WebVitalsReporter from "@/components/WebVitalsReporter";
import { PwaRegister } from "@/components/PwaRegister";
import { AuthProvider } from "@/components/AuthProvider";
import { CookieConsentBanner } from "@/components/CookieConsentBanner";
import { LocaleProvider } from "@/components/LocaleProvider";
import { QueryProvider } from "@/components/QueryProvider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { getSiteUrl } from "@/lib/env";
import { DEFAULT_LOCALE } from "@/lib/locale-constants";
import { createT } from "@/lib/i18n";
import "./globals.css";
import { cn } from "@/lib/utils";

const rootT = createT(DEFAULT_LOCALE);

const inter = Inter({
  subsets: ["latin", "cyrillic"],
  variable: "--font-inter",
  weight: ["400", "500", "600", "700"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL(`${getSiteUrl()}/`),
  manifest: "/manifest.webmanifest",
  title: {
    default: rootT("meta.siteTitle"),
    template: "%s — World Ride Auto",
  },
  description: rootT("meta.siteDescription"),
};

// Root layout НЕ читает cookie/headers → не форсит dynamic-рендер всего сайта.
// `lang` по умолчанию ru; LocaleProvider на клиенте корректирует локаль из cookie.
// Это позволяет ISR для /car (см. car/[ref]/page.tsx). Home/каталог остаются
// динамическими через свой (site)/car layout-метаданные при необходимости.
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang={DEFAULT_LOCALE}
      dir="ltr"
      className={cn("font-sans", inter.variable, geistMono.variable)}
    >
      <body className="antialiased">
        <QueryProvider>
          <LocaleProvider initialLocale={DEFAULT_LOCALE}>
            <AuthProvider>
              <TooltipProvider>
                <WebVitalsReporter />
                {children}
                <PwaRegister />
                <CookieConsentBanner />
              </TooltipProvider>
            </AuthProvider>
          </LocaleProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
