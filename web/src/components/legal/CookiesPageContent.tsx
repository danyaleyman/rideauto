"use client";

import Link from "next/link";
import { useLocaleContext } from "@/components/LocaleProvider";
import { DocLegalChrome } from "@/components/doc-legal/DocLegalChrome";

export function CookiesPageContent() {
  const { t } = useLocaleContext();

  return (
    <DocLegalChrome>
      <main className="doc-wrap">
        <article className="doc-card">
          <h1>{t("legal.cookies.h1")}</h1>
          <p className="muted">{t("legal.cookies.updated")}</p>

          <h2>{t("legal.cookies.s1Title")}</h2>
          <p>{t("legal.cookies.s1p")}</p>

          <h2>{t("legal.cookies.s2Title")}</h2>
          <ul>
            <li>
              <strong>{t("legal.cookies.s2i1")}</strong>
            </li>
            <li>{t("legal.cookies.s2i2")}</li>
            <li>{t("legal.cookies.s2i3")}</li>
          </ul>

          <h2>{t("legal.cookies.s3Title")}</h2>
          <p>{t("legal.cookies.s3p1")}</p>
          <p>{t("legal.cookies.s3p2")}</p>

          <h2>{t("legal.cookies.s4Title")}</h2>
          <p>{t("legal.cookies.s4p")}</p>

          <h2>{t("legal.cookies.s5Title")}</h2>
          <ul>
            <li>
              <Link href="/privacy">{t("legal.privacy.h1")}</Link>
            </li>
            <li>
              <Link href="/agreement">{t("legal.agreement.link")}</Link>
            </li>
          </ul>
        </article>
      </main>
    </DocLegalChrome>
  );
}
