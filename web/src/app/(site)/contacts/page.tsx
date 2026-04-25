import type { Metadata } from "next";
import { MotionFadeUp, MotionStagger, MotionStaggerItem } from "@/components/ui/motion";

export const metadata: Metadata = {
  title: "Contacts",
  description: "World Ride Auto contacts: Telegram, VK and Avito.",
  alternates: { canonical: "/contacts" },
};

export default function ContactsPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <MotionFadeUp>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-900">Contacts</h1>
        <p className="mt-3 max-w-2xl text-zinc-600">
          Reach us in messenger or social channels to discuss budget and options.
        </p>
      </MotionFadeUp>

      <MotionStagger className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MotionStaggerItem>
          <article className="rounded-2xl border border-zinc-200 bg-white p-5">
            <h2 className="text-lg font-semibold">Telegram</h2>
            <p className="mt-2 text-sm">
              Manager: <a className="text-blue-600" href="https://t.me/nikits15" target="_blank" rel="noopener noreferrer">@nikits15</a>
            </p>
            <p className="mt-1 text-sm">
              Channel: <a className="text-blue-600" href="https://t.me/worldrideauto" target="_blank" rel="noopener noreferrer">@worldrideauto</a>
            </p>
          </article>
        </MotionStaggerItem>
        <MotionStaggerItem>
          <article className="rounded-2xl border border-zinc-200 bg-white p-5">
            <h2 className="text-lg font-semibold">VK</h2>
            <p className="mt-2 text-sm">
              <a className="text-blue-600" href="https://vk.com/ride_auto" target="_blank" rel="noopener noreferrer">vk.com/ride_auto</a>
            </p>
          </article>
        </MotionStaggerItem>
        <MotionStaggerItem>
          <article className="rounded-2xl border border-zinc-200 bg-white p-5">
            <h2 className="text-lg font-semibold">Avito</h2>
            <p className="mt-2 text-sm">
              <a className="text-blue-600" href="https://www.avito.ru/brands/8a805bbde7bfbfcc9b9e810b88bb4382?src=sharing" target="_blank" rel="noopener noreferrer">Company profile</a>
            </p>
          </article>
        </MotionStaggerItem>
      </MotionStagger>
    </div>
  );
}
