import type { Metadata } from "next";
import { BuyCalculator } from "@/components/buy/BuyCalculator";

export const metadata: Metadata = {
  title: "How to buy",
  description: "Korea import workflow and rough total cost calculator.",
  alternates: { canonical: "/buy" },
};

export default function BuyPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <h1 className="text-3xl font-semibold tracking-tight text-zinc-900">
        How to buy a car from Korea
      </h1>
      <p className="mt-3 max-w-3xl text-zinc-600">
        We align budget, select options, confirm buyout, then complete shipping and customs.
      </p>

      <ol className="mt-8 grid gap-3 rounded-2xl border border-zinc-200 bg-white p-6 text-sm sm:grid-cols-2">
        <li>1. Consultation and target profile.</li>
        <li>2. Condition checks and final selection.</li>
        <li>3. Buyout and delivery to port.</li>
        <li>4. Customs clearance and handover.</li>
      </ol>

      <div className="mt-8">
        <BuyCalculator />
      </div>
    </div>
  );
}
