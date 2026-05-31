"use client";

import Link from "next/link";
import { useLocaleContext } from "@/components/LocaleProvider";
import { DocLegalChrome } from "@/components/doc-legal/DocLegalChrome";

export function AgreementPageContent() {
  const { t } = useLocaleContext();

  return (
    <DocLegalChrome>
      <main className="doc-wrap">
        <article className="doc-card">
          <h1>{t("legal.agreement.h1")}</h1>
          <p className="legal-meta">{t("legal.agreement.updated")}</p>
          <p>{t("legal.agreement.intro")}</p>

          <h2>{t("legal.agreement.s1Title")}</h2>
          <ul>
            <li>{t("legal.agreement.s1i1")}</li>
            <li>{t("legal.agreement.s1i2")}</li>
          </ul>

          <h2>{t("legal.agreement.s2Title")}</h2>
          <ul>
            <li>{t("legal.agreement.s2i1")}</li>
            <li>{t("legal.agreement.s2i2")}</li>
          </ul>

          <h2>{t("legal.agreement.s3Title")}</h2>
          <ul>
            <li>{t("legal.agreement.s3i1")}</li>
            <li>{t("legal.agreement.s3i2")}</li>
          </ul>

          <h2>{t("legal.agreement.s4Title")}</h2>
          <p>{t("legal.agreement.s4p")}</p>

          <h2>{t("legal.agreement.s5Title")}</h2>
          <p>{t("legal.agreement.s5p")}</p>

          <h2>{t("legal.agreement.s6Title")}</h2>
          <ul>
            <li>
              <Link href="/privacy">{t("legal.privacy.h1")}</Link>
            </li>
            <li>
              <Link href="/cookies">{t("legal.cookies.link")}</Link>
            </li>
          </ul>

          <p className="mt-6">
            <Link href="/catalog">{t("legal.agreement.backCatalog")}</Link>
          </p>
        </article>
      </main>
    </DocLegalChrome>
  );
}
