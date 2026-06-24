import { create } from "zustand";
import type { User } from "@/types/domain";

type AuthState = {
  accessToken?: string;
  refreshToken?: string;
  user?: User;
  setSession: (session: { accessToken: string; refreshToken: string; user: User }) => void;
  clearSession: () => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  setSession: (session) => set(session),
  clearSession: () => set({ accessToken: undefined, refreshToken: undefined, user: undefined }),
}));
