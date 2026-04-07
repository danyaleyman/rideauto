import type { Metadata } from "next";
import Link from "next/link";
import { DocLegalChrome } from "@/components/doc-legal/DocLegalChrome";

export const metadata: Metadata = {
  title: "Политика использования cookie",
  description: "Какие cookie использует сайт World Ride Auto и как управлять согласием.",
  alternates: { canonical: "/cookies" },
};

export default function CookiesPage() {
  return (
    <DocLegalChrome>
      <main className="doc-wrap">
        <article className="doc-card">
          <h1>Политика использования cookie</h1>
          <p className="muted">Актуально на 27.03.2026</p>

          <h2>1. Что такое cookie</h2>
          <p>
            Cookie — это небольшие файлы, которые браузер сохраняет на устройстве пользователя для
            корректной работы сайта и сохранения пользовательских настроек.
          </p>

          <h2>2. Какие cookie используются</h2>
          <ul>
            <li>
              <strong>Необходимые cookie</strong> — обеспечивают базовую работу сайта и не требуют
              отдельного согласия.
            </li>
            <li>
              <strong>Аналитические cookie</strong> — используются только при явном согласии
              пользователя через баннер cookie.
            </li>
          </ul>

          <h2>3. Как управлять согласием</h2>
          <p>
            При первом посещении сайта пользователю предлагается выбор: принять все cookie или
            оставить только необходимые. Выбор сохраняется локально в браузере.
          </p>

          <h2>4. Как отключить cookie в браузере</h2>
          <p>
            Пользователь может удалить или заблокировать cookie в настройках браузера. При этом
            отдельные функции сайта могут работать ограниченно.
          </p>

          <h2>5. Связанные документы</h2>
          <ul>
            <li>
              <Link href="/privacy">Политика конфиденциальности</Link>
            </li>
            <li>
              <Link href="/agreement">Пользовательское соглашение</Link>
            </li>
          </ul>
        </article>
      </main>
    </DocLegalChrome>
  );
}
