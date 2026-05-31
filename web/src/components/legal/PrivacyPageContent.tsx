"use client";

import Link from "next/link";
import { useLocaleContext } from "@/components/LocaleProvider";
import { DocLegalChrome } from "@/components/doc-legal/DocLegalChrome";

export function PrivacyPageContent() {
  const { t } = useLocaleContext();

  return (
    <DocLegalChrome>
      <main className="doc-wrap">
        <article className="doc-card">
          <h1>{t("legal.privacy.h1")}</h1>
          <p className="muted">{t("legal.privacy.updated")}</p>

          <h2>{t("legal.privacy.s1Title")}</h2>
          <p>{t("legal.privacy.s1p")}</p>

          <h2>{t("legal.privacy.s2Title")}</h2>
          <ul>
            <li>{t("legal.privacy.s2i1")}</li>
            <li>{t("legal.privacy.s2i2")}</li>
            <li>
              {t("legal.privacy.s2i3Prefix")}{" "}
              <Link href="/cookies">{t("legal.privacy.s2i3Link")}</Link>.
            </li>
          </ul>

          <h2>{t("legal.privacy.s3Title")}</h2>
          <ul>
            <li>{t("legal.privacy.s3i1")}</li>
            <li>{t("legal.privacy.s3i2")}</li>
            <li>{t("legal.privacy.s3i3")}</li>
          </ul>

          <h2>{t("legal.privacy.s4Title")}</h2>
          <p>{t("legal.privacy.s4p1")}</p>
          <p>{t("legal.privacy.s4p2")}</p>

          <h2>{t("legal.privacy.s5Title")}</h2>
          <p>{t("legal.privacy.s5p1")}</p>
          <p>{t("legal.privacy.s5p2")}</p>

          <h2>{t("legal.privacy.s6Title")}</h2>
          <p>{t("legal.privacy.s6p")}</p>

          <h2>{t("legal.privacy.s7Title")}</h2>
          <p>{t("legal.privacy.s7p")}</p>

          <h2>{t("legal.privacy.s8Title")}</h2>
          <ul>
            <li>
              <Link href="/cookies">{t("legal.cookies.link")}</Link>
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
