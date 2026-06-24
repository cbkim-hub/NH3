import { apiClient } from "./client";
import type { Paginated } from "@/types/common";
import type { Notification } from "@/types/domain";

export const notificationsApi = {
  dashboardAlerts: (params = "page=1&size=10") => apiClient<Paginated<Notification>>(`/dashboard/alerts?${params}`),
};
