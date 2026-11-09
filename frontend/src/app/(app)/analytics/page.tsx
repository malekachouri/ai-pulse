"use client";

import { BarChart3, Database, ServerCrash } from "lucide-react";

import { ActivityChart, DistributionChart } from "@/components/charts/charts";
import { ChartCard } from "@/components/charts/chart-card";
import { StatCard } from "@/components/dashboard/stat-card";
import { TrendingTags } from "@/components/dashboard/trending-tags";
import { PageHeader } from "@/components/layout/page-header";
import { ErrorState } from "@/components/states/states";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ITEM_TYPE_LABEL, SEVERITIES, SEVERITY_COLOR, SEVERITY_LABEL } from "@/lib/labels";
import { useCategories, useDashboard } from "@/lib/queries";
import type { ItemType, Severity } from "@/lib/types";
import { formatDay, titleCase } from "@/lib/utils";

function Empty() {
  return <p className="py-10 text-center text-sm text-muted-foreground">No data yet.</p>;
}

export default function AnalyticsPage() {
  const { data, isLoading, isError, error, refetch } = useDashboard();
  const categories = useCategories();
  const catName = (slug: string) => categories.data?.find((c) => c.slug === slug)?.name ?? titleCase(slug);

  const byType = (data?.by_item_type ?? []).map((d) => ({ label: ITEM_TYPE_LABEL[d.key as ItemType] ?? d.key, count: d.count }));
  const byCat = (data?.by_category ?? []).slice(0, 10).map((d) => ({ label: catName(d.key), count: d.count }));
  const sevMap = new Map((data?.by_severity ?? []).map((d) => [d.key, d.count]));
  const bySev = SEVERITIES.map((s: Severity) => ({ label: SEVERITY_LABEL[s], count: sevMap.get(s) ?? 0, color: SEVERITY_COLOR[s] }));
  const anySev = bySev.some((s) => s.count > 0);

  if (isError)
    return (
      <>
        <PageHeader title="Analytics" icon={BarChart3} />
        <ErrorState error={error} onRetry={() => refetch()} />
      </>
    );

  return (
    <>
      <PageHeader
        title="Analytics"
        description="Statistics computed from collected items. Every chart has a table view."
        icon={BarChart3}
      />
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          <StatCard label="Collected items" value={data?.total_articles} hint="Excluding duplicates" icon={Database} loading={isLoading} />
          <StatCard label="Last 24 hours" value={data?.articles_last_24h} hint="Newly collected" icon={BarChart3} loading={isLoading} />
          <StatCard label="Sources enabled" value={data?.sources_enabled} hint="Active connectors" icon={Database} loading={isLoading} />
          <StatCard
            label="Failing sources"
            value={data?.sources_failing}
            hint="3+ consecutive failures"
            icon={ServerCrash}
            tone={data?.sources_failing ? "critical" : "default"}
            loading={isLoading}
          />
        </div>

        <ChartCard
          title="Collection activity"
          description="Items per day, last 14 days"
          table={{ columns: ["Day", "Items"], rows: (data?.activity_14d ?? []).map((d) => [formatDay(d.day), d.count]) }}
        >
          {isLoading ? <Skeleton className="h-[260px]" /> : <ActivityChart data={data?.activity_14d ?? []} height={260} />}
        </ChartCard>

        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard title="By type" table={{ columns: ["Type", "Items"], rows: byType.map((d) => [d.label, d.count]) }}>
            {isLoading ? <Skeleton className="h-48" /> : byType.length ? <DistributionChart data={byType} /> : <Empty />}
          </ChartCard>
          <ChartCard title="By category (top 10)" table={{ columns: ["Category", "Items"], rows: byCat.map((d) => [d.label, d.count]) }}>
            {isLoading ? <Skeleton className="h-48" /> : byCat.length ? <DistributionChart data={byCat} /> : <Empty />}
          </ChartCard>
          <ChartCard
            title="Severity distribution"
            description="Last 14 days, items with a documented severity"
            table={{ columns: ["Severity", "Items"], rows: bySev.map((d) => [d.label, d.count]) }}
          >
            {isLoading ? (
              <Skeleton className="h-48" />
            ) : anySev ? (
              <DistributionChart data={bySev} colors={bySev.map((s) => s.color)} />
            ) : (
              <Empty />
            )}
          </ChartCard>
          <Card>
            <CardHeader>
              <CardTitle>Trending tags (7 days)</CardTitle>
            </CardHeader>
            <CardContent>{isLoading ? <Skeleton className="h-48" /> : <TrendingTags tags={data?.trending_tags ?? []} />}</CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
