import { BrainCircuit } from "lucide-react";

import { DashboardEmpty, DashboardError, DashboardLoading } from "./dashboard-state";
import { StatusBadge } from "./status-badge";
import type { AiRiskInsight, RiskLevel } from "@/types/dashboard";

export function AiRiskPanel({ insights, level, isLoading, error, onRetry }: { insights: AiRiskInsight[]; level: RiskLevel; isLoading?: boolean; error?: Error | null; onRetry?: () => void }) {
  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-2xl shadow-slate-950/40">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-purple-400/15 p-2 text-purple-200">
            <BrainCircuit className="h-5 w-5" />
          </div>
          <div>
            <h2 className="font-semibold text-white">AI 위험도 분석</h2>
            <p className="text-xs text-slate-400">AI Analysis API 최근 결과</p>
          </div>
        </div>
        <StatusBadge level={level} />
      </div>

      <div className="mt-5 space-y-4">
        {isLoading ? <DashboardLoading label="AI 분석 결과를 불러오는 중입니다" /> : error ? <DashboardError message={error.message} onRetry={onRetry} /> : insights.length === 0 ? <DashboardEmpty label="최근 AI 분석 결과가 없습니다." /> : insights.map((insight) => (
          <div key={insight.label} className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm text-slate-300">{insight.label}</p>
              <strong className="text-xl text-white">{insight.value}</strong>
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-400">{insight.description}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
