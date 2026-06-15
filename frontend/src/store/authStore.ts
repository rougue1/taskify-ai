// Zustand store for authentication state. Access + refresh tokens and the
// current user are persisted to localStorage so a reload keeps the session.
// `hydrated` flips true once persisted state has loaded, so the protected route
// can wait before deciding whether to redirect (avoids a login-page flash).

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import * as api from "@/lib/api";
import type { TokenPair, User } from "@/types";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  hydrated: boolean;

  isAuthenticated: () => boolean;
  setTokens: (tokens: TokenPair) => void;
  clearAuth: () => void;
  markHydrated: () => void;

  register: (email: string, password: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  loadUser: () => Promise<void>;
}

// SSR-safe storage: the getter is only invoked on the client during hydration.
const safeStorage = createJSONStorage(() =>
  typeof window !== "undefined"
    ? window.localStorage
    : (undefined as unknown as Storage),
);

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      hydrated: false,

      isAuthenticated: () => Boolean(get().accessToken),

      setTokens: (tokens) =>
        set({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
        }),

      clearAuth: () => set({ accessToken: null, refreshToken: null, user: null }),

      markHydrated: () => set({ hydrated: true }),

      register: async (email, password) => {
        const tokens = await api.registerRequest(email, password);
        get().setTokens(tokens);
        await get().loadUser();
      },

      login: async (email, password) => {
        const tokens = await api.loginRequest(email, password);
        get().setTokens(tokens);
        await get().loadUser();
      },

      logout: () => get().clearAuth(),

      loadUser: async () => {
        try {
          const user = await api.getMe();
          set({ user });
        } catch {
          get().clearAuth();
        }
      },
    }),
    {
      name: "taskify-auth",
      storage: safeStorage,
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
      }),
      onRehydrateStorage: () => (state) => {
        state?.markHydrated();
      },
    },
  ),
);
