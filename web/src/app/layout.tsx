import type { Metadata } from "next";
import { Geist, Geist_Mono, Inter, Roboto } from "next/font/google";
import WebVitalsReporter from "@/components/WebVitalsReporter";
import { TooltipProvider } from "@/components/ui/tooltip";
import { getSiteUrl } from "@/lib/env";
import "./globals.css";
import { cn } from "@/lib/utils";

const robotoHeading = Roboto({
  subsets: ["latin", "cyrillic"],
  variable: "--font-heading",
  weight: ["400", "500", "700"],
});

const inter = Inter({
  subsets: ["latin", "cyrillic"],
  variable: "--font-inter",
});

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
    <html
      lang="ru"
      dir="ltr"
      className={cn(
        "font-sans",
        inter.variable,
        geistSans.variable,
        geistMono.variable,
        robotoHeading.variable,
      )}
    >
      <body className="antialiased">
        <TooltipProvider>
          <WebVitalsReporter />
          {children}
        </TooltipProvider>
      </body>
    </html>
  );
}
