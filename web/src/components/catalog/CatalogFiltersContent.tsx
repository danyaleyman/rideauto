"use client";

import { useMemo } from "react";
import { CarFront, Gauge, Palette, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { ColorFacetDialog, FacetMultiDropdown } from "@/components/catalog/CatalogFilterPrimitives";
import { RangeBlock } from "@/components/catalog/CatalogBlockWidgets";
import {
  CatalogFilterAccordionSection,
  CatalogFilterFlatSection,
} from "@/components/catalog/CatalogFilterSection";
import { CatalogSavedSearches } from "@/components/catalog/CatalogSavedSearches";
import { MarketSegmentedControl } from "@/components/catalog/MarketSegmentedControl";
import { Accordion } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import type { CatalogSearchController } from "@/hooks/use-catalog-search-state";
import { colorSwatchClass, facetRowLabel } from "@/lib/catalog-client-utils";
import { fuelSortRank, normalizeFuelLabel } from "@/lib/car-detail-data";
import {
  colorFilterSummary,
  conditionFilterSummary,
  rangesFilterSummary,
  techFilterSummary,
  vehicleFilterSummary,
} from "@/lib/catalog-filter-section-summaries";
import { useLocaleContext } from "@/components/LocaleProvider";
import { displayBodyType, displayColor, displayTransmission, transmissionSortRank } from "@/lib/vehicle-spec-locale";
import type { FacetRow } from "@/lib/types";
import { cn } from "@/lib/utils";

function VehicleFacetFields({
  catalog,
}: {
  catalog: CatalogSearchController;
}) {
  const { t, locale } = useLocaleContext();
  const { state, facets, toggle, trimFacetLabelFormatterFn } = catalog;

  if (!facets) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full rounded-xl" />
        <Skeleton className="h-10 w-full rounded-xl" />
        <Skeleton className="h-10 w-full rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <FacetMultiDropdown
        label={t("catalog.filters.mark")}
        rows={facets.marks}
        selected={new Set(state.marks)}
        onToggle={(v) => toggle("marks", v)}
      />
      <FacetMultiDropdown
        label={t("catalog.filters.cluster")}
        rows={facets.clusters ?? []}
        selected={new Set(state.clusters)}
        onToggle={(v) => toggle("clusters", v)}
        disabled={state.marks.length === 0}
      />
      <FacetMultiDropdown
        label={t("catalog.filters.model")}
        rows={facets.models}
        selected={new Set(state.models)}
        onToggle={(v) => toggle("models", v)}
        disabled={state.marks.length === 0}
      />
      <FacetMultiDropdown
        label={t("catalog.filters.generation")}
        rows={facets.generations}
        selected={new Set(state.generations)}
        onToggle={(v) => toggle("generations", v)}
        disabled={state.models.length === 0}
      />
      <FacetMultiDropdown
        label={t("catalog.filters.trim")}
        rows={facets.trims}
        selected={new Set(state.trims)}
        onToggle={(v) => toggle("trims", v)}
        disabled={state.generations.length === 0}
        labelFormatter={trimFacetLabelFormatterFn}
      />
    </div>
  );
}

function ConditionCheckboxes({ catalog }: { catalog: CatalogSearchController }) {
  const { t } = useLocaleContext();
  const { state, navigate } = catalog;
  const items = [
    { key: "drive_awd" as const, label: t("catalog.filters.awdOnly") },
    { key: "power_hp_le_160" as const, label: t("catalog.filters.hp160Only") },
    { key: "no_accidents_only" as const, label: t("catalog.filters.noAccidents") },
    { key: "new_only" as const, label: t("catalog.filters.newOnly") },
  ];
  return (
    <div className="grid gap-2 sm:grid-cols-1">
      {items.map(({ key, label }) => (
        <label
          key={key}
          className="flex min-w-0 cursor-pointer items-start gap-2.5 rounded-xl border border-border/70 bg-background px-3 py-2.5 text-sm leading-snug shadow-sm transition-colors hover:border-primary/30 hover:bg-muted/30"
        >
          <Checkbox
            checked={Boolean(state[key])}
            onCheckedChange={(v) => navigate({ ...state, [key]: Boolean(v), page: 1 })}
            className="mt-0.5 shrink-0"
          />
          <span>{label}</span>
        </label>
      ))}
    </div>
  );
}

function TechFacetFields({ catalog }: { catalog: CatalogSearchController }) {
  const { t, locale } = useLocaleContext();
  const { state, facets, toggle } = catalog;

  if (!facets) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full rounded-xl" />
        <Skeleton className="h-10 w-full rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <FacetMultiDropdown
        label={t("catalog.filters.body")}
        rows={facets.bodies}
        selected={new Set(state.body)}
        onToggle={(v) => toggle("body", v)}
        labelFormatter={(row) => displayBodyType(locale, facetRowLabel(row)) ?? facetRowLabel(row)}
      />
      <FacetMultiDropdown
        label={t("catalog.filters.fuel")}
        rows={facets.fuels}
        selected={new Set(state.fuel)}
        onToggle={(v) => toggle("fuel", v)}
        labelFormatter={(row) => normalizeFuelLabel(facetRowLabel(row)) ?? facetRowLabel(row)}
        comparator={(a, b) => {
          const ra = fuelSortRank(a);
          const rb = fuelSortRank(b);
          if (ra !== rb) return ra - rb;
          return a.localeCompare(b);
        }}
      />
      <FacetMultiDropdown
        label={t("catalog.filters.transmission")}
        rows={facets.transmissions}
        selected={new Set(state.trans)}
        onToggle={(v) => toggle("trans", v)}
        labelFormatter={(row) =>
          displayTransmission(locale, facetRowLabel(row)) ?? facetRowLabel(row)
        }
        comparator={(a, b) => {
          const ra = transmissionSortRank(a);
          const rb = transmissionSortRank(b);
          if (ra !== rb) return ra - rb;
          return a.localeCompare(b, locale === "en" ? "en" : "ru");
        }}
      />
    </div>
  );
}

function ColorFields({ catalog }: { catalog: CatalogSearchController }) {
  const { t, locale } = useLocaleContext();
  const { state, facets, toggle, popularColorRows } = catalog;

  if (!facets) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-20 w-full rounded-xl" />
        <Skeleton className="h-10 w-full rounded-xl" />
      </div>
    );
  }

  return (
    <>
      <div className="rounded-xl border border-border/60 bg-background p-3 shadow-sm">
        <p className="text-xs font-medium text-muted-foreground">{t("catalog.filters.popularColors")}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {popularColorRows.map((row) => {
            const vals = row.values.length ? row.values : [];
            const active = vals.some((v) => state.color.includes(v));
            return (
              <Button
                key={row.label}
                type="button"
                variant={active ? "default" : "outline"}
                size="xs"
                className="min-h-9 rounded-full border-border/80 px-2.5 text-xs font-medium"
                onClick={() => toggle("color", vals)}
              >
                <span
                  className={cn("size-3 shrink-0 rounded-full", colorSwatchClass(row.label))}
                  aria-hidden
                />
                <span className="truncate">{row.label}</span>
              </Button>
            );
          })}
        </div>
      </div>
      <ColorFacetDialog
        label={t("catalog.filters.allColors")}
        rows={facets.colors}
        selected={new Set(state.color)}
        onToggle={(v) => toggle("color", v)}
        labelFormatter={(row) => displayColor(locale, facetRowLabel(row)) ?? facetRowLabel(row)}
      />
    </>
  );
}

/** Тело панели фильтров (desktop sidebar + mobile sheet). */
export function CatalogFiltersContent({
  catalog,
}: {
  catalog: CatalogSearchController;
  inBottomSheet?: boolean;
}) {
  const { t, locale } = useLocaleContext();
  const {
    state,
    facets,
    navigate,
    toggle,
    reset,
    switchMarket,
    popularColorRows,
  } = catalog;

  const facetLabelByValue = useMemo(() => {
    const m = new Map<string, string>();
    if (!facets) return m;
    const add = (rows: FacetRow[]) => {
      for (const r of rows) m.set(r.value, facetRowLabel(r));
    };
    add(facets.marks);
    add(facets.clusters ?? []);
    add(facets.models);
    add(facets.bodies);
    add(facets.fuels);
    add(facets.transmissions);
    add(facets.colors);
    return m;
  }, [facets]);

  const vehicleSummary = vehicleFilterSummary(state, locale);
  const conditionSummary = conditionFilterSummary(state, locale);
  const techSummary = techFilterSummary(state, locale, facetLabelByValue);
  const rangesSummary = rangesFilterSummary(state, locale);
  const colorsSummary = colorFilterSummary(state, facetLabelByValue);

  const vehicleCount =
    state.marks.length +
    state.clusters.length +
    state.models.length +
    state.generations.length +
    state.trims.length;
  const conditionCount = [
    state.drive_awd,
    state.power_hp_le_160,
    state.no_accidents_only,
    state.new_only,
    state.passable_only,
  ].filter(Boolean).length;
  const techCount = state.body.length + state.fuel.length + state.trans.length;
  const colorCount = state.color.length;

  const rangesPanel = (
    <CatalogFilterFlatSection
      icon={Gauge}
      title={t("catalog.filters.ranges")}
      hint={t("catalog.filters.rangesHint")}
      summary={rangesSummary}
      activeCount={
        [
          state.price_from,
          state.price_to,
          state.mileage_from,
          state.mileage_to,
          state.year_from,
          state.year_to,
          state.pricing_tier,
        ].filter((x) => String(x).trim()).length
      }
    >
      <RangeBlock state={state} navigate={navigate} market={state.market} />
    </CatalogFilterFlatSection>
  );

  const accordionBlock = (
    <Accordion
      type="multiple"
      defaultValue={["vehicle", "condition"]}
      className="overflow-visible rounded-2xl border border-border/70 bg-card/40 shadow-sm"
    >
      <CatalogFilterAccordionSection
        value="vehicle"
        icon={CarFront}
        title={t("catalog.filters.vehicle")}
        hint={t("catalog.filters.vehicleHint")}
        summary={vehicleSummary}
        activeCount={vehicleCount}
      >
        <VehicleFacetFields catalog={catalog} />
      </CatalogFilterAccordionSection>

      <CatalogFilterAccordionSection
        value="condition"
        icon={ShieldCheck}
        title={t("catalog.filters.condition")}
        hint={t("catalog.filters.conditionHint")}
        summary={conditionSummary}
        activeCount={conditionCount}
      >
        <ConditionCheckboxes catalog={catalog} />
      </CatalogFilterAccordionSection>

      <CatalogFilterAccordionSection
        value="tech"
        icon={SlidersHorizontal}
        title={t("catalog.filters.tech")}
        hint={t("catalog.filters.techHint")}
        summary={techSummary}
        activeCount={techCount}
      >
        <TechFacetFields catalog={catalog} />
      </CatalogFilterAccordionSection>

      <CatalogFilterAccordionSection
        value="look"
        icon={Palette}
        title={t("catalog.filters.appearance")}
        hint={t("catalog.filters.colorHint")}
        summary={colorsSummary}
        activeCount={colorCount}
        className="border-b-0"
      >
        <ColorFields catalog={catalog} />
      </CatalogFilterAccordionSection>
    </Accordion>
  );

  const desktopFlatSections = (
    <div className="hidden flex-col gap-3 lg:flex">
      <CatalogFilterFlatSection
        icon={CarFront}
        title={t("catalog.filters.vehicle")}
        hint={t("catalog.filters.vehicleHint")}
        summary={vehicleSummary}
        activeCount={vehicleCount}
      >
        <VehicleFacetFields catalog={catalog} />
      </CatalogFilterFlatSection>
      <CatalogFilterFlatSection
        icon={ShieldCheck}
        title={t("catalog.filters.condition")}
        hint={t("catalog.filters.conditionHint")}
        summary={conditionSummary}
        activeCount={conditionCount}
      >
        <ConditionCheckboxes catalog={catalog} />
      </CatalogFilterFlatSection>
      <CatalogFilterFlatSection
        icon={SlidersHorizontal}
        title={t("catalog.filters.tech")}
        hint={t("catalog.filters.techHint")}
        summary={techSummary}
        activeCount={techCount}
      >
        <TechFacetFields catalog={catalog} />
      </CatalogFilterFlatSection>
      <CatalogFilterFlatSection
        icon={Palette}
        title={t("catalog.filters.appearance")}
        hint={t("catalog.filters.colorHint")}
        summary={colorsSummary}
        activeCount={colorCount}
      >
        <ColorFields catalog={catalog} />
      </CatalogFilterFlatSection>
    </div>
  );

  return (
    <div className="flex max-w-full flex-col gap-3">
      <MarketSegmentedControl market={state.market} onChange={switchMarket} />
      <CatalogSavedSearches catalog={catalog} />
      {rangesPanel}
      <div className="lg:hidden">{accordionBlock}</div>
      {desktopFlatSections}
      <Button type="button" variant="outline" className="w-full shrink-0 rounded-xl" onClick={reset}>
        {t("catalog.filters.reset")}
      </Button>
    </div>
  );
}
