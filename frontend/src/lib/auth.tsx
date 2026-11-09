"use client";

import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, refreshAccessToken, setAccessToken } from "@/lib/api";
import type { TokenResponse, User } from "@/lib/types";

type Status = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  user: User | null;
  status: Status;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  reload: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const qc = useQueryClient();

  const loadMe = useCallback(async () => {
    try {
      const me = await api.get<User>("/auth/me");
      setUser(me);
      setStatus("authenticated");
    } catch {
      setUser(null);
      setStatus("anonymous");
    }
  }, []);

  // Restore the session from the httpOnly refresh cookie on first load.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = await refreshAccessToken();
      if (cancelled) return;
      if (token) await loadMe();
      else setStatus("anonymous");
    })();
    return () => {
      cancelled = true;
    };
  }, [loadMe]);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await api.post<TokenResponse>("/auth/login", { email, password });
      setAccessToken(tokens.access_token);
      const me = await api.get<User>("/auth/me");
      setUser(me);
      setStatus("authenticated");
      await qc.invalidateQueries();
      return me;
    },
    [qc],
  );

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setAccessToken(null);
      setUser(null);
      setStatus("anonymous");
      qc.clear();
    }
  }, [qc]);

  const value = useMemo(
    () => ({ user, status, login, logout, reload: loadMe }),
    [user, status, login, logout, loadMe],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
