import { apiClient } from "./client";
import type { Paginated } from "@/types/common";
import type { Sensor } from "@/types/domain";

export const sensorsApi = {
  list: (params = "page=1&size=12") => apiClient<Paginated<Sensor>>(`/sensors?${params}`),
  detail: (id: string) => apiClient<Sensor>(`/sensors/${id}`),
};
