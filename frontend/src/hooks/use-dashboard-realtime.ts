"use client";

import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/auth-store";

export type DashboardRealtimeEvent = {
  id: string;
  type:
    | "Connected"
    | "SensorDataReceived"
    | "RiskEventCreated"
    | "NotificationCreated"
    | "AIAnalysisCompleted"
    | "ActionWorkOrderCreated"
    | "ActionWorkOrderUpdated"
    | "ActionWorkOrderClosed";
  payload: Record<string, unknown>;
  occurredAt: string;
};

type RealtimeStatus = "connecting" | "connected" | "disconnected" | "error";

function websocketUrl(accessToken?: string) {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
  const url = new URL(apiBaseUrl.replace(/^http/, "ws"));
  url.pathname = `${url.pathname.replace(/\/$/, "")}/ws/dashboard`;
  if (accessToken) {
    url.searchParams.set("token", accessToken);
  }
  return url.toString();
}

export function useDashboardRealtime() {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((state: { accessToken?: string }) => state.accessToken);
  const [status, setStatus] = useState<RealtimeStatus>("connecting");
  const [lastEvent, setLastEvent] = useState<DashboardRealtimeEvent | null>(null);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const url = useMemo(() => websocketUrl(accessToken), [accessToken]);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let closedByEffect = false;
    let attempts = 0;
    let connect: () => void;

    const invalidateDashboardQueries = (event: DashboardRealtimeEvent) => {
      if (event.type === "SensorDataReceived") {
        queryClient.invalidateQueries({ queryKey: ["dashboard", "sensors"] });
      }
      if (event.type === "RiskEventCreated") {
        queryClient.invalidateQueries({ queryKey: ["dashboard", "risk-event-stats"] });
        queryClient.invalidateQueries({ queryKey: ["dashboard", "risk-events"] });
      }
      if (event.type === "NotificationCreated") {
        queryClient.invalidateQueries({ queryKey: ["dashboard", "notifications"] });
      }
      if (event.type === "AIAnalysisCompleted") {
        queryClient.invalidateQueries({ queryKey: ["dashboard", "ai-analysis"] });
        queryClient.invalidateQueries({ queryKey: ["dashboard", "risk-event-stats"] });
        if (event.payload.riskEventCreated) {
          queryClient.invalidateQueries({ queryKey: ["dashboard", "risk-events"] });
        }
      }
      if (
        event.type === "ActionWorkOrderCreated" ||
        event.type === "ActionWorkOrderUpdated" ||
        event.type === "ActionWorkOrderClosed"
      ) {
        queryClient.invalidateQueries({ queryKey: ["dashboard", "risk-event-stats"] });
        queryClient.invalidateQueries({ queryKey: ["dashboard", "risk-events"] });
        queryClient.invalidateQueries({ queryKey: ["dashboard", "notifications"] });
      }
    };

    const scheduleReconnect = () => {
      if (closedByEffect) return;
      attempts += 1;
      const delay = Math.min(30_000, 1_000 * 2 ** Math.min(attempts, 5));
      reconnectTimer = setTimeout(() => {
        setReconnectAttempt(attempts);
        connect();
      }, delay);
    };

    connect = () => {
      setStatus("connecting");
      socket = new WebSocket(url);

      socket.onopen = () => {
        attempts = 0;
        setReconnectAttempt(0);
        setStatus("connected");
      };
      socket.onerror = () => setStatus("error");
      socket.onclose = () => {
        setStatus("disconnected");
        scheduleReconnect();
      };
      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data) as DashboardRealtimeEvent;
          setLastEvent(event);
          invalidateDashboardQueries(event);
        } catch {
          setStatus("error");
        }
      };
    };

    connect();

    return () => {
      closedByEffect = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      socket?.close();
    };
  }, [queryClient, url]);

  return { status, lastEvent, reconnectAttempt };
}
