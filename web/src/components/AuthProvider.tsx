"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo } from "react";
import { authKeys } from "@/hooks/auth-query-keys";
import { fetchMeClient, logoutClient, requestMagicLinkClient, verifyMagicLinkClient } from "@/lib/client-api";
import type { AuthUser } from "@/lib/types";

type AuthContextValue = {
  loading: boolean;
  authenticated: boolean;
  user: AuthUser | null;
  refresh: () => Promise<void>;
  requestMagicLink: (email: string) => Promise<void>;
  verifyMagicLink: (token: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const AUTH_ME_STALE_MS = 60_000;

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const meQuery = useQuery({
    queryKey: authKeys.me(),
    queryFn: ({ signal }) => fetchMeClient({ signal }),
    staleTime: AUTH_ME_STALE_MS,
    retry: false,
  });

  const user = meQuery.data?.authenticated ? meQuery.data.user : null;
  const loading = meQuery.isPending;

  const refresh = useCallback(async () => {
    await meQuery.refetch();
  }, [meQuery]);

  const requestMagicLink = useCallback(async (email: string) => {
    await requestMagicLinkClient(email);
  }, []);

  const verifyMagicLink = useCallback(
    async (token: string) => {
      await verifyMagicLinkClient(token);
      await meQuery.refetch();
    },
    [meQuery],
  );

  const logout = useCallback(async () => {
    await logoutClient();
    queryClient.setQueryData(authKeys.me(), { authenticated: false, user: null });
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      loading,
      authenticated: !!user,
      user,
      refresh,
      requestMagicLink,
      verifyMagicLink,
      logout,
    }),
    [loading, user, refresh, requestMagicLink, verifyMagicLink, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
