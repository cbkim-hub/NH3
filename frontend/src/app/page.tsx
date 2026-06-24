import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-3xl font-bold">NH3 지하배관 모니터링 MVP</h1>
      <p className="text-slate-600">Phase 1: 인증, 대시보드, 배관 관리, 센서 관리</p>
      <Link href="/dashboard">
        <Button>대시보드로 이동</Button>
      </Link>
    </main>
  );
}
