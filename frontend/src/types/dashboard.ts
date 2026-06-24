export type RiskLevel = "critical" | "warning" | "normal";

export type KpiCardData = {
  label: string;
  value: string;
  change: string;
  tone: RiskLevel;
};

export type PipelineRisk = {
  rank: number;
  name: string;
  district: string;
  riskScore: number;
  status: RiskLevel;
  material: string;
  diameterMm: number;
};

export type RealtimeEvent = {
  id: string;
  time: string;
  title: string;
  description: string;
  severity: RiskLevel;
  sensorCode: string;
};

export type SensorStatus = {
  id: string;
  name: string;
  type: string;
  status: "online" | "warning" | "offline";
  value: string;
  unit: string;
  trend: "up" | "down" | "flat";
};

export type AiRiskInsight = {
  label: string;
  value: string;
  description: string;
  tone: RiskLevel;
};

export type MapAsset = {
  id: string;
  name: string;
  coordinates: [number, number];
  risk: RiskLevel;
  type: "pipeline" | "sensor";
};

export type PipelinePath = {
  id: string;
  name: string;
  coordinates: [number, number][];
  risk: RiskLevel;
};
