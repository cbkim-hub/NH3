import { AlertTriangle, Loader2, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";

export function DashboardLoading({ label = "데이터를 불러오는 중입니다" }: { label?: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 text-sm text-slate-300">
      <div className="flex items-center gap-2">
        <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />
        {label}
      </div>
    </div>
  );
}

export function DashboardError({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-5 text-sm text-red-100">
      <div className="flex items-center gap-2 font-semibold">
        <AlertTriangle className="h-4 w-4" /> API 연결 오류
      </div>
      <p className="mt-2 text-xs text-red-100/80">
        {message ?? "Backend API에서 데이터를 가져오지 못했습니다."}
      </p>
      {onRetry ? (
        <Button
          type="button"
          variant="outline"
          className="mt-4 border-red-300/40 bg-red-950/40 text-red-100 hover:bg-red-900/50"
          onClick={onRetry}
        >
          <RefreshCcw className="mr-2 h-4 w-4" /> 다시 시도
        </Button>
      ) : null}
    </div>
  );
}

export function DashboardEmpty({ label = "표시할 데이터가 없습니다." }: { label?: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 text-sm text-slate-400">
      {label}
    </div>
  );
}
