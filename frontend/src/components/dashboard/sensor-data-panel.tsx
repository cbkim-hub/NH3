import { ArrowDown, ArrowRight, ArrowUp, RadioTower } from "lucide-react";

import { DashboardEmpty, DashboardError, DashboardLoading } from "./dashboard-state";
import type { SensorStatus } from "@/types/dashboard";

const statusClass = {
  online: "bg-emerald-400 text-emerald-950",
  warning: "bg-amber-400 text-amber-950",
  offline: "bg-red-400 text-red-950",
};

const trendIcon = {
  up: ArrowUp,
  down: ArrowDown,
  flat: ArrowRight,
};

export function SensorDataPanel({ sensors, isLoading, error, onRetry }: { sensors: SensorStatus[]; isLoading?: boolean; error?: Error | null; onRetry?: () => void }) {
  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-cyan-400/15 p-2 text-cyan-200">
            <RadioTower className="h-5 w-5" />
          </div>
          <div>
            <h2 className="font-semibold text-white">실시간 센서 데이터</h2>
            <p className="text-xs text-slate-400">Sensor API 기반 센서 상태</p>
          </div>
        </div>
        <span className="text-xs text-slate-500">API polling 30초</span>
      </div>

      {isLoading ? <DashboardLoading label="센서 상태를 불러오는 중입니다" /> : error ? <DashboardError message={error.message} onRetry={onRetry} /> : sensors.length === 0 ? <DashboardEmpty label="등록된 센서가 없습니다." /> : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          {sensors.map((sensor) => {
            const Trend = trendIcon[sensor.trend];
            return (
              <article key={sensor.id} className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-white">{sensor.name}</p>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${statusClass[sensor.status]}`}>
                    {sensor.status}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500">{sensor.type}</p>
                <div className="mt-4 flex items-end justify-between">
                  <div>
                    <strong className="text-2xl text-white">{sensor.value}</strong>
                    <span className="ml-1 text-xs text-slate-400">{sensor.unit}</span>
                  </div>
                  <Trend className="h-5 w-5 text-cyan-300" />
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
