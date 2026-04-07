import Link from "next/link";

export default function Home() {
  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
        Prod Encar
      </h1>
      <p className="mt-4 text-lg text-zinc-600 dark:text-zinc-400">
        Каталог на Next.js: SSR для первой отрисовки, фильтры и пагинация в браузере через FastAPI,
        Meilisearch и PostgreSQL.
      </p>
      <div className="mt-10 flex flex-col gap-4">
        <Link
          className="inline-flex items-center justify-center rounded-xl bg-blue-600 px-5 py-3 text-center font-medium text-white hover:bg-blue-700"
          href="/catalog"
        >
          Открыть каталог
        </Link>
        <p className="text-sm text-zinc-500">
          Статические страницы (о компании, юридические) по-прежнему в папке{" "}
          <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">frontend/</code> и отдаются
          тем же доменом (см. деплой).
        </p>
      </div>
    </div>
  );
}
