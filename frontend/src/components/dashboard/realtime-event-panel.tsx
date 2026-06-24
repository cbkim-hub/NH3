import { BellRing } from "lucide-react";

import { DashboardEmpty, DashboardError, DashboardLoading } from "./dashboard-state";
import { StatusBadge } from "./status-badge";
import type { RealtimeEvent } from "@/types/dashboard";

export function RealtimeEventPanel({ events, isLoading, error, onRetry }: { events: RealtimeEvent[]; isLoading?: boolean; error?: Error | null; onRetry?: () => void }) {
  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-900/90 p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-red-400/15 p-2 text-red-200">
            <BellRing className="h-5 w-5" />
          </div>
          <div>
            <h2 className="font-semibold text-white">실시간 이벤트</h2>
            <p className="text-xs text-slate-400">Risk Event API 기반 최근 이벤트</p>
          </div>
        </div>
        <span className="flex items-center gap-2 rounded-full bg-red-500/10 px-3 py-1 text-xs font-semibold text-red-200">
          <span className="h-2 w-2 animate-pulse rounded-full bg-red-400" /> LIVE
        </span>
      </div>

      {isLoading ? <DashboardLoading label="위험 이벤트를 불러오는 중입니다" /> : error ? <DashboardError message={error.message} onRetry={onRetry} /> : events.length === 0 ? <DashboardEmpty label="최근 위험 이벤트가 없습니다." /> : (
        <div className="space-y-3">
          {events.map((event) => (
            <article key={event.id} className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-white">{event.title}</p>
                  <p className="mt-1 text-xs text-slate-400">{event.description}</p>
                </div>
                <StatusBadge level={event.severity} />
              </div>
              <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                <span>{event.sensorCode}</span>
                <span>{event.time}</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
