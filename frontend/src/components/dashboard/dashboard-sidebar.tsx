import { Activity, Bell, Gauge, Map, RadioTower, Route, Settings, ShieldAlert } from "lucide-react";

const menuItems = [
  { label: "관제 대시보드", icon: Gauge, active: true },
  { label: "GIS 지도", icon: Map },
  { label: "배관 관리", icon: Route },
  { label: "센서 관리", icon: RadioTower },
  { label: "AI 위험도", icon: ShieldAlert },
  { label: "알림", icon: Bell },
  { label: "시스템", icon: Settings },
];

export function DashboardSidebar() {
  return (
    <aside className="hidden w-72 shrink-0 border-r border-slate-800 bg-slate-950/95 p-5 text-slate-100 lg:flex lg:flex-col">
      <div className="mb-8 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-cyan-400/15 text-cyan-300 ring-1 ring-cyan-300/30">
          <Activity className="h-6 w-6" />
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-cyan-300">NH3 AI Ops</p>
          <h1 className="text-lg font-bold">지하배관 관제</h1>
        </div>
      </div>

      <nav className="space-y-2">
        {menuItems.map((item) => (
          <button
            key={item.label}
            className={`flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm transition ${
              item.active
                ? "bg-cyan-400/15 text-cyan-100 ring-1 ring-cyan-300/30"
                : "text-slate-400 hover:bg-slate-900 hover:text-slate-100"
            }`}
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </button>
        ))}
      </nav>

      <div className="mt-auto rounded-3xl border border-cyan-300/20 bg-cyan-300/10 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">관제 상태</p>
        <p className="mt-3 text-2xl font-bold text-white">LIVE</p>
        <p className="mt-1 text-xs leading-5 text-slate-300">1,354개 센서와 812km 배관망을 실시간 모니터링 중입니다.</p>
      </div>
    </aside>
  );
}
