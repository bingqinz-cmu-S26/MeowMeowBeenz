import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import * as api from '@/lib/api';
import * as authStorage from '@/lib/authStorage';
import type { AuthUser } from '@/types';

type AuthContextValue = {
  user: AuthUser | null;
  booting: boolean;
  authLoading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [booting, setBooting] = useState(true);
  const [authLoading, setAuthLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const bootstrap = useCallback(async () => {
    setBooting(true);
    try {
      const token = await authStorage.getToken();
      if (!token) {
        setUser(null);
        return;
      }
      api.setAuthToken(token);
      const currentUser = await api.fetchCurrentUser();
      setUser(currentUser);
    } catch {
      await authStorage.clearToken();
      api.setAuthToken(null);
      setUser(null);
    } finally {
      setBooting(false);
    }
  }, []);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const login = useCallback(async (username: string, password: string) => {
    setAuthLoading(true);
    setError(null);
    try {
      const result = await api.login(username, password);
      await authStorage.setToken(result.token);
      api.setAuthToken(result.token);
      setUser(result.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed.');
      throw err;
    } finally {
      setAuthLoading(false);
    }
  }, []);

  const register = useCallback(async (username: string, password: string, displayName?: string) => {
    setAuthLoading(true);
    setError(null);
    try {
      const result = await api.register(username, password, displayName);
      await authStorage.setToken(result.token);
      api.setAuthToken(result.token);
      setUser(result.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed.');
      throw err;
    } finally {
      setAuthLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    await authStorage.clearToken();
    api.setAuthToken(null);
    setUser(null);
    setError(null);
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const value = useMemo(
    () => ({
      user,
      booting,
      authLoading,
      error,
      login,
      register,
      logout,
      clearError,
    }),
    [user, booting, authLoading, error, login, register, logout, clearError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
