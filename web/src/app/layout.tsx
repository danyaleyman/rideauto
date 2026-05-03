import type { Metadata } from "next";
import { Geist_Mono, Inter } from "next/font/google";
import WebVitalsReporter from "@/components/WebVitalsReporter";
import { CookieConsentBanner } from "@/components/CookieConsentBanner";
import { AuthProvider } from "@/components/AuthProvider";
import { LocaleProvider } from "@/components/LocaleProvider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { getSiteUrl } from "@/lib/env";
import { getServerLocale } from "@/lib/locale-server";
import "./globals.css";
import { cn } from "@/lib/utils";

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
  title: {
    default: "World Ride Auto — авто из Азии",
    template: "%s — World Ride Auto",
  },
  description:
    "Автомобили из Кореи и Азии с доставкой во Владивосток. Каталог, фильтры, цены и оформление через World Ride Auto.",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const locale = await getServerLocale();
  return (
    <html lang={locale} dir="ltr" className={cn("font-sans", inter.variable, geistMono.variable)}>
      <body className="antialiased">
        <LocaleProvider initialLocale={locale}>
          <AuthProvider>
            <TooltipProvider>
              <WebVitalsReporter />
              {children}
              <CookieConsentBanner />
            </TooltipProvider>
          </AuthProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
