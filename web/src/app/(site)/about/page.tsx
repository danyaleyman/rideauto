import type { Metadata } from "next";
import Link from "next/link";
import { MotionFadeUp, MotionStagger, MotionStaggerItem } from "@/components/ui/motion";

export const metadata: Metadata = {
  title: "About",
  description: "World Ride Auto company profile and delivery workflow.",
  alternates: { canonical: "/about" },
};

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <MotionFadeUp>
        <section className="rounded-2xl border border-zinc-200 bg-white p-8">
          <h1 className="text-3xl font-semibold tracking-tight text-zinc-900">
            About World Ride Auto
          </h1>
          <p className="mt-4 text-zinc-600">
            We source cars from Korea and China, verify condition, then handle shipping,
            customs, and handover in Russia.
          </p>
        </section>
      </MotionFadeUp>

      <MotionStagger className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["45+", "cars delivered in last 6 months"],
          ["One desk", "selection, buyout, logistics, docs"],
          ["Transparent", "clear estimates and milestones"],
          ["Support", "manager in Telegram at each step"],
        ].map(([k, v]) => (
          <MotionStaggerItem key={k}>
            <article className="rounded-xl border border-zinc-200 bg-zinc-50 p-4">
              <p className="text-2xl font-semibold text-zinc-900">{k}</p>
              <p className="mt-1 text-sm text-zinc-600">{v}</p>
            </article>
          </MotionStaggerItem>
        ))}
      </MotionStagger>

      <MotionFadeUp delay={0.06}>
        <section className="mt-6 rounded-2xl border border-zinc-200 bg-white p-8">
          <h2 className="text-xl font-semibold text-zinc-900">How we work</h2>
          <ol className="mt-4 list-decimal space-y-2 pl-5 text-zinc-600">
            <li>We define budget and required car profile.</li>
            <li>We shortlist options and confirm purchase decision.</li>
            <li>We complete buyout, shipping, customs, and delivery.</li>
          </ol>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/catalog" className="rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white">
              Open catalog
            </Link>
            <a
              href="https://t.me/nikits15"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-xl border border-zinc-300 px-5 py-3 text-sm font-semibold text-zinc-800"
            >
              Contact manager
            </a>
          </div>
        </section>
      </MotionFadeUp>
    </div>
  );
}
