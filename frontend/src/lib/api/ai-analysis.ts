import { apiClient } from "./client";
import type { AIAnalysis } from "@/types/domain";

export const aiAnalysisApi = {
  recent: (limit = 5) => apiClient<AIAnalysis[]>(`/ai-analysis/recent?limit=${limit}`),
};
