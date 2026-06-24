import { DashboardEmpty, DashboardError, DashboardLoading } from "./dashboard-state";
import { StatusBadge } from "./status-badge";
import type { PipelineRisk } from "@/types/dashboard";

export function RiskyPipelines({ pipelines, isLoading, error, onRetry }: { pipelines: PipelineRisk[]; isLoading?: boolean; error?: Error | null; onRetry?: () => void }) {
  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-white">위험 배관 TOP 10</h2>
          <p className="text-xs text-slate-400">Risk Event API의 pipelineId / riskScore 기준</p>
        </div>
      </div>
      {isLoading ? <DashboardLoading label="위험 배관 목록을 계산 중입니다" /> : error ? <DashboardError message={error.message} onRetry={onRetry} /> : pipelines.length === 0 ? <DashboardEmpty label="위험 배관 데이터가 없습니다." /> : (
        <div className="max-h-[360px] space-y-2 overflow-auto pr-1">
          {pipelines.map((pipeline) => (
            <div key={`${pipeline.rank}-${pipeline.name}`} className="grid grid-cols-[2rem_1fr_auto] items-center gap-3 rounded-2xl border border-slate-800 bg-slate-950/70 p-3">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-800 text-xs font-bold text-slate-200">{pipeline.rank}</span>
              <div>
                <p className="text-sm font-semibold text-slate-100">{pipeline.name}</p>
                <p className="text-xs text-slate-500">{pipeline.district} · {pipeline.material} · Ø{pipeline.diameterMm}</p>
              </div>
              <div className="text-right">
                <p className="text-sm font-bold text-white">{pipeline.riskScore}</p>
                <StatusBadge level={pipeline.status} className="mt-1 inline-block" />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
