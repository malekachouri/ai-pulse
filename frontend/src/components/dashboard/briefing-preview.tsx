"use client";

import { ArrowUpRight, Sparkles, Sunrise } from "lucide-react";
import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useLatestBriefing } from "@/lib/queries";
import { formatDateTime } from "@/lib/utils";

export function BriefingPreview() {
  const { data, isLoading, isError } = useLatestBriefing();
  return (
    <Card className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-brand-blue/10 via-transparent to-brand-violet/10" />
      <CardHeader className="relative">
        <CardTitle className="flex items-center gap-2">
          <Sunrise className="size-4 text-primary dark:text-blue-300" /> Daily briefing
        </CardTitle>
        <Link href="/briefing" className="inline-flex items-center gap-0.5 text-xs text-primary hover:underline">
          Open <ArrowUpRight className="size-3" />
        </Link>
      </CardHeader>
      <CardContent className="relative">
        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-4" />
            <Skeleton className="h-4 w-4/5" />
          </div>
        ) : isError ? (
          <p className="text-sm text-muted-foreground">Couldn&apos;t load the latest briefing.</p>
        ) : !data ? (
          <p className="text-sm text-muted-foreground">
            No briefing has been generated yet. Briefings are produced automatically once data collection and the AI
            engine are running.
          </p>
        ) : (
          <>
            <p className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-violet-700 dark:text-violet-300">
              <Sparkles className="size-3.5" /> AI-generated · {formatDateTime(data.generated_at)}
            </p>
            <p className="line-clamp-4 text-sm leading-relaxed">{data.executive_summary ?? "No summary available."}</p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
