import { describe, expect, it } from "vitest";
import { listingChipVariants } from "@/components/ui/listing-chip";

describe("listingChipVariants", () => {
  it("includes elevated commerce tones", () => {
    expect(listingChipVariants({ tone: "commerceEmerald" })).toContain("emerald");
    expect(listingChipVariants({ tone: "overlay" })).toContain("rounded-2xl");
  });

  it("uses caption size for md chips", () => {
    expect(listingChipVariants({ size: "md" })).toContain("text-caption");
    expect(listingChipVariants({ size: "md" })).toContain("h-8");
  });
});
