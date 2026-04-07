import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "About",
  description: "World Ride Auto company profile and delivery workflow.",
  alternates: { canonical: "/about" },
};

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <section className="rounded-2xl border border-zinc-200 bg-white p-8 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          About World Ride Auto
        </h1>
        <p className="mt-4 text-zinc-600 dark:text-zinc-400">
          We source cars from Korea and China, verify condition, then handle shipping,
          customs, and handover in Russia.
        </p>
      </section>

      <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["45+", "cars delivered in last 6 months"],
          ["One desk", "selection, buyout, logistics, docs"],
          ["Transparent", "clear estimates and milestones"],
          ["Support", "manager in Telegram at each step"],
        ].map(([k, v]) => (
          <article key={k} className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900">
            <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">{k}</p>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{v}</p>
          </article>
        ))}
      </section>

      <section className="mt-6 rounded-2xl border border-zinc-200 bg-white p-8 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
        <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">How we work</h2>
        <ol className="mt-4 list-decimal space-y-2 pl-5 text-zinc-600 dark:text-zinc-400">
          <li>We define budget and required car profile.</li>
          <li>We shortlist options and confirm purchase decision.</li>
          <li>We complete buyout, shipping, customs, and delivery.</li>
        </ol>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/catalog" className="rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-700">
            Open catalog
          </Link>
          <a
            href="https://t.me/nikits15"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-xl border border-zinc-300 px-5 py-3 text-sm font-semibold text-zinc-800 hover:bg-zinc-50 dark:border-zinc-600 dark:text-zinc-100 dark:hover:bg-zinc-900"
          >
            Contact manager
          </a>
        </div>
      </section>
    </div>
  );
}
