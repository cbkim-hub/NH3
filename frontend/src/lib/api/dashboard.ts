import { apiClient } from "./client";
import type { DashboardOverview } from "@/types/domain";

export const dashboardApi = {
  overview: () => apiClient<DashboardOverview>("/dashboard/overview"),
  alerts: (params = "page=1&size=10") => apiClient(`/dashboard/alerts?${params}`),
};
