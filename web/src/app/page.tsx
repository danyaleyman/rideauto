import Link from "next/link";

export default function Home() {
  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-6 py-16">
      <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
        Prod Encar
      </h1>
      <p className="mt-3 text-lg text-zinc-600 dark:text-zinc-400">
        Фронтенд на Next.js (SSR + гидратация): каталог запрашивает тот же FastAPI, что и
        статическая витрина.
      </p>
      <ul className="mt-10 flex flex-col gap-3 text-base">
        <li>
          <Link
            className="font-medium text-blue-600 hover:underline dark:text-blue-400"
            href="/catalog"
          >
            Каталог (SSR)
          </Link>
          <span className="ml-2 text-sm text-zinc-500">
            — список через Meilisearch, карточки из Postgres
          </span>
        </li>
        <li className="text-sm text-zinc-500">
          С legacy UI: каталог в <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">frontend/</code> по-прежнему может указывать на{" "}
          <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">/api/search</code>.
        </li>
      </ul>
    </div>
  );
}
