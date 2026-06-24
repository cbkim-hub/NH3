import { DashboardEmpty, DashboardError, DashboardLoading } from "./dashboard-state";
import type { KpiCardData } from "@/types/dashboard";

const toneClass = {
  critical: "from-red-500/20 to-red-500/5 text-red-100 ring-red-400/30",
  warning: "from-amber-500/20 to-amber-500/5 text-amber-100 ring-amber-400/30",
  normal: "from-cyan-500/20 to-blue-500/5 text-cyan-100 ring-cyan-400/20",
};

type KpiCardsProps = {
  items: KpiCardData[];
  isLoading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
};

export function KpiCards({ items, isLoading, error, onRetry }: KpiCardsProps) {
  if (isLoading) {
    return <DashboardLoading label="KPI 통계를 불러오는 중입니다" />;
  }
  if (error) {
    return <DashboardError message={error.message} onRetry={onRetry} />;
  }
  if (items.length === 0) {
    return <DashboardEmpty label="표시할 KPI 데이터가 없습니다." />;
  }

  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {items.map((kpi) => (
        <article key={kpi.label} className={`rounded-3xl bg-gradient-to-br p-5 ring-1 ${toneClass[kpi.tone]}`}>
          <p className="text-sm text-slate-300">{kpi.label}</p>
          <div className="mt-3 flex items-end justify-between">
            <strong className="text-3xl font-bold text-white">{kpi.value}</strong>
            <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-medium">{kpi.change}</span>
          </div>
        </article>
      ))}
    </section>
  );
}
