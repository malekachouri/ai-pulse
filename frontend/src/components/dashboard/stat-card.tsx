import type { LucideIcon } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatCount } from "@/lib/utils";

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "default",
  loading,
}: {
  label: string;
  value: number | undefined;
  hint: string;
  icon: LucideIcon;
  tone?: "default" | "critical";
  loading?: boolean;
}) {
  return (
    <Card className="relative overflow-hidden p-4 transition-shadow hover:shadow-md sm:p-5">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground sm:text-sm">{label}</p>
        <span
          className={cn(
            "rounded-lg p-1.5",
            tone === "critical" ? "bg-sev-critical/12 text-sev-critical" : "bg-primary/10 text-primary dark:text-blue-300",
          )}
        >
          <Icon className="size-4" />
        </span>
      </div>
      {loading || value === undefined ? (
        <Skeleton className="mt-3 h-8 w-16" />
      ) : (
        <p className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{formatCount(value)}</p>
      )}
      <p className="mt-1 text-[11px] text-muted-foreground sm:text-xs">{hint}</p>
    </Card>
  );
}
