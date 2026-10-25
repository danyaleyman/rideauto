import { describe, expect, it } from "vitest";
import { childFacetLabelFormatter, facetLabelSetsEqual } from "@/lib/catalog-active-chips";
import type { FacetRow } from "@/lib/types";

const row = (value: string, label = value): FacetRow => ({ value, label, count: 1 });

describe("facetLabelSetsEqual", () => {
  it("treats BMW line and model lists as the same", () => {
    const clusters = [row("3 Series"), row("5 Series")];
    const models = [row("3 Series"), row("5 Series")];
    expect(facetLabelSetsEqual(clusters, models)).toBe(true);
  });

  it("keeps distinct family vs model", () => {
    expect(facetLabelSetsEqual([row("RB")], [row("Solaris"), row("Accent")])).toBe(false);
  });
});

describe("childFacetLabelFormatter", () => {
  it("strips selected brand from model labels", () => {
    const fmt = childFacetLabelFormatter(["Volkswagen"]);
    expect(fmt(row("Volkswagen Beetle 2013 1.2TSI Comfort"))).toBe("Beetle 2013 1.2TSI Comfort");
  });
});
