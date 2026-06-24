"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { AiRiskPanel } from "@/components/dashboard/ai-risk-panel";
import { DashboardMap } from "@/components/dashboard/dashboard-map";
import { DashboardSidebar } from "@/components/dashboard/dashboard-sidebar";
import { KpiCards } from "@/components/dashboard/kpi-cards";
import { RealtimeEventPanel } from "@/components/dashboard/realtime-event-panel";
import { RiskyPipelines } from "@/components/dashboard/risky-pipelines";
import { SensorDataPanel } from "@/components/dashboard/sensor-data-panel";
import { useDashboardRealtime } from "@/hooks/use-dashboard-realtime";
import { aiAnalysisApi } from "@/lib/api/ai-analysis";
import { notificationsApi } from "@/lib/api/notifications";
import { pipelinesApi } from "@/lib/api/pipelines";
import { riskEventsApi } from "@/lib/api/risk-events";
import { sensorsApi } from "@/lib/api/sensors";
import type { AiRiskInsight, KpiCardData, MapAsset, PipelinePath, PipelineRisk, RealtimeEvent, RiskLevel, SensorStatus } from "@/types/dashboard";
import type { AIAnalysis, Notification, Pipeline, RiskEvent, RiskEventStats, Sensor } from "@/types/domain";

function toRiskLevel(severity?: string): RiskLevel {
  if (severity === "Critical" || severity === "High") return "critical";
  if (severity === "Medium" || severity === "Low" || severity === "Warning") return "warning";
  return "normal";
}

function formatRelativeTime(value?: string | null) {
  if (!value) return "-";
  const diff = Date.now() - new Date(value).getTime();
  const minutes = Math.max(0, Math.round(diff / 60_000));
  if (minutes < 1) return "방금 전";
  if (minutes < 60) return `${minutes}분 전`;
  return `${Math.round(minutes / 60)}시간 전`;
}

function buildKpis(
  stats?: RiskEventStats,
  pipelines?: Pipeline[],
  sensors?: Sensor[],
  notifications?: Notification[],
  ai?: AIAnalysis[],
): KpiCardData[] {
  const activeNotifications = notifications?.filter((item) => item.status !== "Read").length ?? 0;
  const onlineSensors = sensors?.filter((sensor) => sensor.status === "Online").length ?? 0;
  const latestRiskScore = ai?.[0]?.riskScore ?? stats?.averageRiskScore ?? 0;
  return [
    { label: "Open Risk Events", value: String(stats?.open ?? 0), change: `${stats?.critical ?? 0} Critical`, tone: (stats?.critical ?? 0) > 0 ? "critical" : "normal" },
    { label: "평균 AI 위험도", value: latestRiskScore.toFixed(1), change: `High ${stats?.high ?? 0}`, tone: latestRiskScore >= 75 ? "critical" : latestRiskScore >= 50 ? "warning" : "normal" },
    { label: "온라인 센서", value: String(onlineSensors), change: `${sensors?.length ?? 0} loaded`, tone: "normal" },
    { label: "관리 배관", value: String(pipelines?.length ?? 0), change: `${activeNotifications} alerts`, tone: activeNotifications > 0 ? "warning" : "normal" },
  ];
}

function mapRiskEvents(events?: RiskEvent[]): RealtimeEvent[] {
  return (events ?? []).map((event) => ({
    id: event.id,
    title: event.title,
    description: event.description ?? `${event.status} · Risk Score ${event.riskScore}`,
    severity: toRiskLevel(event.severity),
    sensorCode: event.sensorId ? `Sensor ${event.sensorId.slice(0, 8)}` : event.eventCode,
    time: formatRelativeTime(event.detectedAt),
  }));
}

function mapSensors(sensors?: Sensor[]): SensorStatus[] {
  return (sensors ?? []).map((sensor) => ({
    id: sensor.id,
    name: sensor.name,
    type: sensor.sensorType,
    status: sensor.status === "Online" ? "online" : sensor.status === "Warning" ? "warning" : "offline",
    value: sensor.status === "Online" ? "LIVE" : sensor.status,
    unit: sensor.unit,
    trend: sensor.sensorType === "Pressure" || sensor.sensorType === "Leakage" ? "down" : sensor.sensorType === "Vibration" ? "up" : "flat",
  }));
}

function mapAiInsights(analyses?: AIAnalysis[]): AiRiskInsight[] {
  const latest = analyses?.[0];
  if (!latest) return [];
  const signals = latest.evidence?.signals as Record<string, { detected?: boolean; reason?: string; scoreContribution?: number }> | undefined;
  return [
    { label: "최근 Risk Score", value: latest.riskScore.toFixed(1), description: `${latest.modelName} · ${latest.severity} · ${formatRelativeTime(latest.createdAt)}`, tone: toRiskLevel(latest.severity) },
    ...Object.entries(signals ?? {}).slice(0, 3).map(([key, signal]) => ({
      label: key,
      value: signal.detected ? "Detected" : "Normal",
      description: `${signal.reason ?? "evidence"} · +${signal.scoreContribution ?? 0}`,
      tone: (signal.detected ? "warning" : "normal") as RiskLevel,
    })),
  ];
}

function buildRiskyPipelines(events?: RiskEvent[], pipelines?: Pipeline[]): PipelineRisk[] {
  const pipelineMap = new Map((pipelines ?? []).map((pipeline) => [pipeline.id, pipeline]));
  const grouped = new Map<string, { score: number; count: number }>();
  for (const event of events ?? []) {
    const key = event.pipelineId ?? "미지정 배관";
    const current = grouped.get(key) ?? { score: 0, count: 0 };
    grouped.set(key, { score: Math.max(current.score, event.riskScore), count: current.count + 1 });
  }
  return [...grouped.entries()]
    .sort((a, b) => b[1].score - a[1].score)
    .slice(0, 10)
    .map(([pipelineId, value], index) => ({
      rank: index + 1,
      name: pipelineId === "미지정 배관" ? pipelineId : pipelineMap.get(pipelineId)?.name ?? `Pipeline ${pipelineId.slice(0, 8)}`,
      district: `${value.count} events`,
      material: pipelineId === "미지정 배관" ? "N/A" : pipelineMap.get(pipelineId)?.material ?? "API",
      diameterMm: pipelineId === "미지정 배관" ? 0 : pipelineMap.get(pipelineId)?.diameterMm ?? 0,
      riskScore: Math.round(value.score),
      status: value.score >= 75 ? "critical" : value.score >= 50 ? "warning" : "normal",
    }));
}

const riskRank: Record<RiskLevel, number> = { normal: 0, warning: 1, critical: 2 };

function maxRisk(current: RiskLevel | undefined, next: RiskLevel): RiskLevel {
  if (!current) return next;
  return riskRank[next] > riskRank[current] ? next : current;
}

function buildPipelinePaths(pipelines?: Pipeline[], events?: RiskEvent[]): PipelinePath[] {
  const eventRiskByPipeline = new Map<string, RiskLevel>();
  for (const event of events ?? []) {
    if (!event.pipelineId) continue;
    eventRiskByPipeline.set(
      event.pipelineId,
      maxRisk(eventRiskByPipeline.get(event.pipelineId), toRiskLevel(event.severity)),
    );
  }
  return (pipelines ?? [])
    .filter((pipeline) => pipeline.geometry?.coordinates?.length)
    .map((pipeline) => ({
      id: pipeline.id,
      name: pipeline.name,
      coordinates: pipeline.geometry!.coordinates,
      risk: eventRiskByPipeline.get(pipeline.id) ?? toRiskLevel(pipeline.riskGrade === "D" || pipeline.riskGrade === "E" ? "Medium" : "Normal"),
    }));
}

function buildMapAssets(events?: RiskEvent[], sensors?: Sensor[]): MapAsset[] {
  const eventAssets = (events ?? []).filter((event) => event.location?.coordinates).map((event) => ({
    id: event.id,
    name: event.title,
    coordinates: event.location!.coordinates,
    risk: toRiskLevel(event.severity),
    type: "pipeline" as const,
  }));
  const sensorAssets = (sensors ?? []).filter((sensor) => sensor.geometry?.coordinates).map((sensor) => ({
    id: sensor.id,
    name: sensor.name,
    coordinates: sensor.geometry!.coordinates,
    risk: (sensor.status === "Critical" ? "critical" : sensor.status === "Warning" ? "warning" : "normal") as RiskLevel,
    type: "sensor" as const,
  }));
  return [...eventAssets, ...sensorAssets];
}

export default function DashboardPage() {
  const realtime = useDashboardRealtime();
  const statsQuery = useQuery({ queryKey: ["dashboard", "risk-event-stats"], queryFn: riskEventsApi.stats });
  const recentEventsQuery = useQuery({ queryKey: ["dashboard", "risk-events", "recent"], queryFn: () => riskEventsApi.recent(10) });
  const riskEventsQuery = useQuery({ queryKey: ["dashboard", "risk-events", "list"], queryFn: () => riskEventsApi.list("page=1&size=100&sortBy=riskScore&sortOrder=desc") });
  const pipelinesQuery = useQuery({ queryKey: ["dashboard", "pipelines"], queryFn: () => pipelinesApi.list("page=1&size=100") });
  const alertsQuery = useQuery({ queryKey: ["dashboard", "notifications"], queryFn: () => notificationsApi.dashboardAlerts("page=1&size=10") });
  const aiQuery = useQuery({ queryKey: ["dashboard", "ai-analysis", "recent"], queryFn: () => aiAnalysisApi.recent(5) });
  const sensorsQuery = useQuery({ queryKey: ["dashboard", "sensors"], queryFn: () => sensorsApi.list("page=1&size=12") });

  const kpis = useMemo(() => buildKpis(statsQuery.data, pipelinesQuery.data?.items, sensorsQuery.data?.items, alertsQuery.data?.items, aiQuery.data), [statsQuery.data, pipelinesQuery.data, sensorsQuery.data, alertsQuery.data, aiQuery.data]);
  const events = useMemo(() => mapRiskEvents(recentEventsQuery.data), [recentEventsQuery.data]);
  const sensorCards = useMemo(() => mapSensors(sensorsQuery.data?.items), [sensorsQuery.data]);
  const aiInsights = useMemo(() => mapAiInsights(aiQuery.data), [aiQuery.data]);
  const riskyPipelines = useMemo(() => buildRiskyPipelines(riskEventsQuery.data?.items, pipelinesQuery.data?.items), [riskEventsQuery.data, pipelinesQuery.data]);
  const mapAssets = useMemo(() => buildMapAssets(recentEventsQuery.data, sensorsQuery.data?.items), [recentEventsQuery.data, sensorsQuery.data]);
  const pipelinePaths = useMemo(() => buildPipelinePaths(pipelinesQuery.data?.items, riskEventsQuery.data?.items), [pipelinesQuery.data, riskEventsQuery.data]);

  const isKpiLoading = statsQuery.isLoading || pipelinesQuery.isLoading || sensorsQuery.isLoading || alertsQuery.isLoading || aiQuery.isLoading;
  const kpiError = statsQuery.error ?? pipelinesQuery.error ?? sensorsQuery.error ?? alertsQuery.error ?? aiQuery.error;
  const isMapLoading = pipelinesQuery.isLoading || sensorsQuery.isLoading || recentEventsQuery.isLoading;
  const mapError = pipelinesQuery.error ?? sensorsQuery.error ?? recentEventsQuery.error;
  const retryDashboard = () => {
    void statsQuery.refetch();
    void pipelinesQuery.refetch();
    void sensorsQuery.refetch();
    void alertsQuery.refetch();
    void aiQuery.refetch();
    void recentEventsQuery.refetch();
    void riskEventsQuery.refetch();
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="flex min-h-screen">
        <DashboardSidebar />
        <section className="flex min-w-0 flex-1 flex-col gap-5 p-4 lg:p-6">
          <header className="flex flex-col justify-between gap-3 rounded-3xl border border-slate-800 bg-slate-900/70 p-5 md:flex-row md:items-center">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-cyan-300">Phase 1 Dashboard</p>
              <h1 className="mt-2 text-2xl font-bold text-white md:text-3xl">AI 기반 지하배관 실시간 관제</h1>
              <p className="mt-1 text-sm text-slate-400">Backend API 기반으로 위험도, 센서, 이벤트, 알림, AI 분석을 통합 모니터링합니다.</p>
            </div>
            <div className="rounded-2xl border border-emerald-400/30 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-100">
              운영 모드 · WebSocket {realtime.status}
            </div>
            {realtime.lastEvent ? (
              <p className="mt-2 text-xs text-emerald-100/80 md:mt-0">최근 이벤트: {realtime.lastEvent.type}</p>
            ) : null}
          </header>

          <KpiCards items={kpis} isLoading={isKpiLoading} error={kpiError} onRetry={retryDashboard} />

          <div className="grid min-h-0 flex-1 gap-5 xl:grid-cols-[1fr_420px]">
            <div className="flex min-w-0 flex-col gap-5">
              <DashboardMap mapAssets={mapAssets} pipelinePaths={pipelinePaths} isLoading={isMapLoading} error={mapError} onRetry={retryDashboard} />
              <SensorDataPanel sensors={sensorCards} isLoading={sensorsQuery.isLoading} error={sensorsQuery.error} onRetry={() => void sensorsQuery.refetch()} />
            </div>
            <aside className="flex flex-col gap-5">
              <RealtimeEventPanel events={events} isLoading={recentEventsQuery.isLoading} error={recentEventsQuery.error} onRetry={() => void recentEventsQuery.refetch()} />
              <AiRiskPanel insights={aiInsights} level={toRiskLevel(aiQuery.data?.[0]?.severity)} isLoading={aiQuery.isLoading} error={aiQuery.error} onRetry={() => void aiQuery.refetch()} />
              <RiskyPipelines pipelines={riskyPipelines} isLoading={riskEventsQuery.isLoading || pipelinesQuery.isLoading} error={riskEventsQuery.error ?? pipelinesQuery.error} onRetry={() => { void riskEventsQuery.refetch(); void pipelinesQuery.refetch(); }} />
            </aside>
          </div>
        </section>
      </div>
    </main>
  );
}
