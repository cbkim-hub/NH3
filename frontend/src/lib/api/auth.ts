import { apiClient } from "./client";
import type { User } from "@/types/domain";

export type LoginRequest = { email: string; password: string };
export type LoginResponse = { accessToken: string; refreshToken: string; user: User };

export const authApi = {
  login: (body: LoginRequest) => apiClient<LoginResponse>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  me: () => apiClient<User>("/auth/me"),
};
