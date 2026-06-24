import { useAuthStore } from "@/stores/auth-store";
import type { ApiResponse } from "@/types/common";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

function getAccessToken() {
  if (typeof window === "undefined") {
    return undefined;
  }
  return useAuthStore.getState().accessToken ?? window.localStorage.getItem("accessToken") ?? undefined;
}

export async function apiClient<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });
  const payload = (await response.json()) as ApiResponse<T>;
  if (!response.ok || payload.error) {
    throw new Error(payload.error?.message ?? `API request failed: ${response.status}`);
  }
  return payload.data;
}
