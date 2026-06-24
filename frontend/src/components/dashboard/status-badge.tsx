import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { RiskLevel } from "@/types/dashboard";

const riskLabel: Record<RiskLevel, string> = {
  critical: "위험",
  warning: "주의",
  normal: "정상",
};

const riskClass: Record<RiskLevel, string> = {
  critical: "border-red-400/50 bg-red-500/15 text-red-200",
  warning: "border-amber-400/50 bg-amber-500/15 text-amber-100",
  normal: "border-emerald-400/50 bg-emerald-500/15 text-emerald-100",
};

export function StatusBadge({ level, className }: { level: RiskLevel; className?: string }) {
  return (
    <Badge className={cn(riskClass[level], className)}>
      {riskLabel[level]}
    </Badge>
  );
}
