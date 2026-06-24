import { apiClient } from "./client";
import type { Paginated } from "@/types/common";
import type { RiskEvent, RiskEventStats } from "@/types/domain";

export const riskEventsApi = {
  stats: () => apiClient<RiskEventStats>("/risk-events/stats"),
  recent: (limit = 10) => apiClient<RiskEvent[]>(`/risk-events/recent?limit=${limit}`),
  list: (params = "page=1&size=20") => apiClient<Paginated<RiskEvent>>(`/risk-events?${params}`),
};
