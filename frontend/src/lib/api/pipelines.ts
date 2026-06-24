import { apiClient } from "./client";
import type { Paginated } from "@/types/common";
import type { Pipeline } from "@/types/domain";

export const pipelinesApi = {
  list: (params = "page=1&size=20") => apiClient<Paginated<Pipeline>>(`/pipelines?${params}`),
  detail: (id: string) => apiClient<Pipeline>(`/pipelines/${id}`),
};
