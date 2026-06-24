"use client";

import { Layers, LocateFixed, ThermometerSun } from "lucide-react";
import maplibregl from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { DashboardError, DashboardLoading } from "./dashboard-state";
import type { MapAsset, PipelinePath } from "@/types/dashboard";

const riskColor = {
  critical: "#ef4444",
  warning: "#f59e0b",
  normal: "#10b981",
};

type DashboardMapProps = {
  mapAssets: MapAsset[];
  pipelinePaths: PipelinePath[];
  isLoading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
};

function pipelineCollection(pipelinePaths: PipelinePath[]) {
  return {
    type: "FeatureCollection" as const,
    features: pipelinePaths.map((pipeline) => ({
      type: "Feature" as const,
      properties: { id: pipeline.id, name: pipeline.name, risk: pipeline.risk },
      geometry: { type: "LineString" as const, coordinates: pipeline.coordinates },
    })),
  };
}

function assetCollection(mapAssets: MapAsset[]) {
  return {
    type: "FeatureCollection" as const,
    features: mapAssets.map((asset) => ({
      type: "Feature" as const,
      properties: { id: asset.id, name: asset.name, risk: asset.risk, type: asset.type },
      geometry: { type: "Point" as const, coordinates: asset.coordinates },
    })),
  };
}

export function DashboardMap({ mapAssets, pipelinePaths, isLoading, error, onRetry }: DashboardMapProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const pipelinePathsRef = useRef(pipelinePaths);
  const mapAssetsRef = useRef(mapAssets);
  const [heatmapEnabled, setHeatmapEnabled] = useState(true);

  useEffect(() => {
    pipelinePathsRef.current = pipelinePaths;
  }, [pipelinePaths]);

  useEffect(() => {
    mapAssetsRef.current = mapAssets;
  }, [mapAssets]);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      center: [127.0276, 37.5326],
      zoom: 11,
      pitch: 44,
      bearing: -18,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
          },
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
      },
    });

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");
    mapRef.current = map;

    map.on("load", () => {
      map.addSource("pipeline-lines", {
        type: "geojson",
        data: pipelineCollection(pipelinePathsRef.current),
      });

      map.addLayer({
        id: "pipeline-glow",
        type: "line",
        source: "pipeline-lines",
        paint: {
          "line-color": ["match", ["get", "risk"], "critical", riskColor.critical, "warning", riskColor.warning, riskColor.normal],
          "line-width": 10,
          "line-opacity": 0.2,
          "line-blur": 4,
        },
      });

      map.addLayer({
        id: "pipeline-lines",
        type: "line",
        source: "pipeline-lines",
        paint: {
          "line-color": ["match", ["get", "risk"], "critical", riskColor.critical, "warning", riskColor.warning, riskColor.normal],
          "line-width": ["match", ["get", "risk"], "critical", 5, 4],
          "line-opacity": 0.92,
        },
      });

      map.addSource("pipeline-risk", {
        type: "geojson",
        data: assetCollection(mapAssetsRef.current),
      });

      map.addLayer({
        id: "risk-heatmap",
        type: "heatmap",
        source: "pipeline-risk",
        paint: {
          "heatmap-weight": ["match", ["get", "risk"], "critical", 1, "warning", 0.65, 0.25],
          "heatmap-intensity": 1.2,
          "heatmap-radius": 44,
          "heatmap-opacity": 0.72,
          "heatmap-color": ["interpolate", ["linear"], ["heatmap-density"], 0, "rgba(14,165,233,0)", 0.35, "rgba(250,204,21,0.55)", 0.7, "rgba(249,115,22,0.75)", 1, "rgba(239,68,68,0.9)"],
        },
      });

      map.addLayer({
        id: "asset-points",
        type: "circle",
        source: "pipeline-risk",
        paint: {
          "circle-radius": ["match", ["get", "type"], "sensor", 7, 10],
          "circle-color": ["match", ["get", "risk"], "critical", riskColor.critical, "warning", riskColor.warning, riskColor.normal],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 2,
          "circle-opacity": 0.92,
        },
      });

      map.addLayer({
        id: "asset-labels",
        type: "symbol",
        source: "pipeline-risk",
        layout: {
          "text-field": ["get", "name"],
          "text-size": 12,
          "text-offset": [0, 1.2],
          "text-anchor": "top",
        },
        paint: {
          "text-color": "#f8fafc",
          "text-halo-color": "#020617",
          "text-halo-width": 1.4,
        },
      });
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);


  useEffect(() => {
    const map = mapRef.current;
    const source = map?.getSource("pipeline-lines") as maplibregl.GeoJSONSource | undefined;
    if (source) {
      source.setData(pipelineCollection(pipelinePaths));
    }
  }, [pipelinePaths]);

  useEffect(() => {
    const map = mapRef.current;
    const source = map?.getSource("pipeline-risk") as maplibregl.GeoJSONSource | undefined;
    if (source) {
      source.setData(assetCollection(mapAssets));
    }
  }, [mapAssets]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer("risk-heatmap")) {
      return;
    }
    map.setLayoutProperty("risk-heatmap", "visibility", heatmapEnabled ? "visible" : "none");
  }, [heatmapEnabled]);

  return (
    <section className="relative min-h-[520px] overflow-hidden rounded-[2rem] border border-slate-800 bg-slate-950 shadow-2xl shadow-slate-950/60">
      <div ref={mapContainerRef} className="absolute inset-0" />
      {isLoading ? (
        <div className="absolute inset-x-5 top-24 z-10">
          <DashboardLoading label="GIS 데이터를 불러오는 중입니다" />
        </div>
      ) : null}
      {error ? (
        <div className="absolute inset-x-5 top-24 z-10">
          <DashboardError message={error.message} onRetry={onRetry} />
        </div>
      ) : null}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-slate-950/30 via-transparent to-slate-950/70" />

      <div className="absolute left-5 top-5 rounded-3xl border border-slate-700/70 bg-slate-950/85 p-4 text-white backdrop-blur">
        <p className="text-xs uppercase tracking-[0.2em] text-cyan-300">GIS Risk Map</p>
        <h2 className="mt-1 text-xl font-bold">서울 지하배관 AI 위험도</h2>
        <p className="mt-1 text-xs text-slate-400">배관·센서·이상 이벤트 통합 관제</p>
      </div>

      <div className="absolute right-5 top-5 flex flex-col gap-3">
        <Button variant="outline" className="border-slate-700 bg-slate-950/85 text-slate-100 backdrop-blur hover:bg-slate-900">
          <LocateFixed className="mr-2 h-4 w-4" /> 현재 관제권역
        </Button>
        <div className="flex items-center justify-between gap-3 rounded-2xl border border-slate-700 bg-slate-950/85 px-4 py-3 text-sm font-semibold text-slate-100 backdrop-blur">
          <span className="flex items-center gap-2"><ThermometerSun className="h-4 w-4 text-red-300" /> Heatmap</span>
          <Switch checked={heatmapEnabled} onCheckedChange={setHeatmapEnabled} aria-label="위험도 heatmap 레이어 토글" />
        </div>
      </div>

      <div className="absolute bottom-5 left-5 right-5 grid gap-3 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-700/70 bg-slate-950/85 p-4 backdrop-blur">
          <div className="flex items-center gap-2 text-sm font-semibold text-white"><Layers className="h-4 w-4 text-cyan-300" /> 활성 레이어</div>
          <p className="mt-2 text-xs text-slate-400">배관 위험도 · 센서 상태 · AI heatmap</p>
        </div>
        <div className="rounded-2xl border border-red-400/30 bg-red-500/15 p-4 backdrop-blur">
          <p className="text-xs text-red-100">Critical 구간</p>
          <p className="text-2xl font-bold text-white">{mapAssets.filter((asset) => asset.risk === "critical").length}</p>
        </div>
        <div className="rounded-2xl border border-amber-400/30 bg-amber-500/15 p-4 backdrop-blur">
          <p className="text-xs text-amber-100">Warning 구간</p>
          <p className="text-2xl font-bold text-white">{mapAssets.filter((asset) => asset.risk === "warning").length}</p>
        </div>
      </div>
    </section>
  );
}
