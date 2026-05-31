"use client";

import { useCallback, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/components/AuthProvider";
import { useLocaleContext } from "@/components/LocaleProvider";
import {
  catalogStateKey,
  catalogStateToSubscriptionFilters,
  parseCatalogUrl,
  stateToBrowserUrl,
  type CatalogUrlState,
} from "@/lib/catalog-url";
import {
  createSubscriptionClient,
  deleteSubscriptionClient,
  fetchSubscriptionsClient,
  patchSubscriptionClient,
  type SubscriptionItem,
} from "@/lib/client-api";
import {
  clearSavedSearchesLocal,
  readSavedSearchesLocal,
  SAVED_SEARCHES_MAX,
  type LocalSavedSearch,
} from "@/lib/saved-searches-storage";

export type SavedCatalogSearch = LocalSavedSearch & {
  notifyEnabled?: boolean;
  serverSynced?: boolean;
};

function persistLocal(items: SavedCatalogSearch[]) {
  localStorage.setItem(
    "wra-saved-catalog-searches-v1",
    JSON.stringify(items.slice(0, SAVED_SEARCHES_MAX)),
  );
}

function serverToLocal(row: SubscriptionItem): SavedCatalogSearch {
  return {
    id: row.id,
    name: row.name,
    query: row.query_string,
    market: row.market === "china" ? "china" : "korea",
    createdAt: row.created_at || new Date().toISOString(),
    notifyEnabled: row.notify_enabled,
    serverSynced: true,
  };
}

export const savedSearchKeys = {
  all: ["saved-catalog-searches"] as const,
};

export function useSavedCatalogSearches() {
  const { authenticated, loading: authLoading } = useAuth();
  const queryClient = useQueryClient();
  const [localItems, setLocalItems] = useState<SavedCatalogSearch[]>([]);
  const [importDone, setImportDone] = useState(false);

  useEffect(() => {
    if (!authenticated) {
      setLocalItems(readSavedSearchesLocal());
      setImportDone(false);
    }
  }, [authenticated]);

  const serverQuery = useQuery({
    queryKey: savedSearchKeys.all,
    queryFn: ({ signal }) => fetchSubscriptionsClient({ signal }),
    enabled: authenticated,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!authenticated || authLoading || importDone) return;
    const local = readSavedSearchesLocal();
    if (!local.length) {
      setImportDone(true);
      return;
    }
    void (async () => {
      for (const item of local) {
        const state = parseCatalogUrl(new URLSearchParams(item.query));
        try {
          await createSubscriptionClient({
            name: item.name,
            filters: catalogStateToSubscriptionFilters(state),
            query_string: item.query,
            market: item.market,
            notify_enabled: true,
          });
        } catch {
          // skip failed rows
        }
      }
      clearSavedSearchesLocal();
      setImportDone(true);
      await queryClient.invalidateQueries({ queryKey: savedSearchKeys.all });
    })();
  }, [authenticated, authLoading, importDone, queryClient]);

  const items: SavedCatalogSearch[] = authenticated
    ? (serverQuery.data?.result ?? []).map(serverToLocal)
    : localItems;

  const { t } = useLocaleContext();

  const saveCurrent = useCallback(
    async (state: CatalogUrlState, name?: string) => {
      const query = stateToBrowserUrl(state);
      const label =
        name?.trim() ||
        (state.q
          ? t("savedSearch.nameQuery", { q: state.q })
          : state.marks.length
            ? state.marks.join(", ")
            : state.market === "china"
              ? t("savedSearch.nameChina")
              : t("savedSearch.nameKorea"));

      if (authenticated) {
        await createSubscriptionClient({
          name: label,
          filters: catalogStateToSubscriptionFilters(state),
          query_string: query,
          market: state.market,
          notify_enabled: true,
        });
        await queryClient.invalidateQueries({ queryKey: savedSearchKeys.all });
        return;
      }

      const entry: SavedCatalogSearch = {
        id: `${Date.now()}-${catalogStateKey(state).slice(0, 32)}`,
        name: label,
        query,
        market: state.market,
        createdAt: new Date().toISOString(),
      };
      setLocalItems((prev) => {
        const deduped = prev.filter((x) => x.query !== entry.query);
        const next = [entry, ...deduped].slice(0, SAVED_SEARCHES_MAX);
        persistLocal(next);
        return next;
      });
    },
    [authenticated, queryClient],
  );

  const remove = useCallback(
    async (id: string) => {
      if (authenticated) {
        await deleteSubscriptionClient(id);
        await queryClient.invalidateQueries({ queryKey: savedSearchKeys.all });
        return;
      }
      setLocalItems((prev) => {
        const next = prev.filter((x) => x.id !== id);
        persistLocal(next);
        return next;
      });
    },
    [authenticated, queryClient],
  );

  const setNotifyEnabled = useCallback(
    async (id: string, enabled: boolean) => {
      if (!authenticated) return;
      await patchSubscriptionClient(id, { notify_enabled: enabled });
      await queryClient.invalidateQueries({ queryKey: savedSearchKeys.all });
    },
    [authenticated, queryClient],
  );

  const hrefFor = useCallback((item: SavedCatalogSearch) => {
    const qs = item.query.trim();
    return qs ? `/catalog?${qs}` : "/catalog";
  }, []);

  const stateFromItem = useCallback((item: SavedCatalogSearch): CatalogUrlState => {
    return parseCatalogUrl(new URLSearchParams(item.query));
  }, []);

  return {
    items,
    saveCurrent,
    remove,
    setNotifyEnabled,
    hrefFor,
    stateFromItem,
    loading: authenticated && serverQuery.isLoading,
    notifyByEmail: authenticated,
  };
}
