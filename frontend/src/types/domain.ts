import type { ID } from "./common";

export type PointGeometry = { type: "Point"; coordinates: [number, number] };
export type LineStringGeometry = { type: "LineString"; coordinates: [number, number][] };

export type User = {
  id: ID;
  email: string;
  name: string;
  organizationId?: ID | null;
  roleCodes: string[];
  permissionCodes?: string[];
};

export type Pipeline = {
  id: ID;
  code: string;
  name: string;
  pipelineType: string;
  material?: string | null;
  diameterMm?: number | null;
  riskGrade?: "A" | "B" | "C" | "D" | "E" | null;
  geometry?: LineStringGeometry;
};

export type Sensor = {
  id: ID;
  pipelineId?: ID | null;
  sensorCode: string;
  name: string;
  sensorType: "Pressure" | "Flow" | "Vibration" | "Leakage" | "Temperature";
  unit: string;
  status: "Online" | "Offline" | "Warning" | "Critical";
  lastSeenAt?: string | null;
  geometry?: PointGeometry;
};

export type RiskEvent = {
  id: ID;
  eventCode: string;
  title: string;
  description?: string | null;
  pipelineId?: ID | null;
  sensorId?: ID | null;
  severity: "Normal" | "Low" | "Medium" | "High" | "Critical";
  riskScore: number;
  status: "Open" | "Investigating" | "InProgress" | "Resolved" | "Closed";
  location?: PointGeometry | null;
  detectedAt: string;
  resolvedAt?: string | null;
  evidence?: Record<string, unknown>;
};

export type RiskEventStats = {
  total: number;
  open: number;
  investigating: number;
  inProgress: number;
  resolved: number;
  closed: number;
  critical: number;
  high: number;
  averageRiskScore: number;
};

export type Notification = {
  id: ID;
  riskEventId?: ID | null;
  recipientId?: ID | null;
  channel: "InApp" | "Email" | "SMS" | string;
  title: string;
  message: string;
  status: "Pending" | "Sent" | "Failed" | "Read" | string;
  sentAt?: string | null;
  readAt?: string | null;
  payload?: Record<string, unknown>;
  createdAt: string;
};

export type AIAnalysis = {
  id: ID;
  pipelineId?: ID | null;
  sensorId?: ID | null;
  modelName: string;
  modelVersion: string;
  analysisType: string;
  riskScore: number;
  severity: "Normal" | "Low" | "Medium" | "High" | "Critical";
  startedAt: string;
  endedAt?: string | null;
  evidence: Record<string, unknown>;
  createdAt: string;
};

export type DashboardOverview = {
  activeAlerts: number;
  criticalAlerts: number;
  activeSensors: number;
  pipelineCount: number;
};
