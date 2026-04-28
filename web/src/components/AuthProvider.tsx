"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
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

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<AuthUser | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchMeClient();
      setUser(res.authenticated ? res.user : null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const requestMagicLink = useCallback(async (email: string) => {
    await requestMagicLinkClient(email);
  }, []);

  const verifyMagicLink = useCallback(async (token: string) => {
    await verifyMagicLinkClient(token);
    await refresh();
  }, [refresh]);

  const logout = useCallback(async () => {
    await logoutClient();
    setUser(null);
  }, []);

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
