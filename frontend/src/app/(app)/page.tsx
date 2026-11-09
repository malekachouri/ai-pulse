"use client";

import { Activity, Bug, Cpu, LayoutDashboard, Newspaper, ShieldAlert, Siren } from "lucide-react";
import Link from "next/link";

import { ActivityChart, DistributionChart } from "@/components/charts/charts";
import { ChartCard } from "@/components/charts/chart-card";
import { BriefingPreview } from "@/components/dashboard/briefing-preview";
import { CompactArticleList } from "@/components/dashboard/compact-list";
import { StatCard } from "@/components/dashboard/stat-card";
import { TrendingTags } from "@/components/dashboard/trending-tags";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState, ErrorState } from "@/components/states/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ITEM_TYPE_LABEL } from "@/lib/labels";
import { useDashboard } from "@/lib/queries";
import type { ItemType } from "@/lib/types";
import { formatDay, safeUrl, timeAgo } from "@/lib/utils";

export default function OverviewPage() {
  const { data, isLoading, isError, error, refetch } = useDashboard();

  const distribution = (data?.by_item_type ?? []).map((d) => ({
    label: ITEM_TYPE_LABEL[d.key as ItemType] ?? d.key,
    count: d.count,
  }));
  const noData = data && data.total_articles === 0;

  return (
    <>
      <PageHeader
        title="Overview"
        description="What's new, what changed, what failed — across AI, security and infrastructure."
        icon={LayoutDashboard}
      />

      {isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-5">
            <StatCard label="Collected items" value={data?.total_articles} hint={`${data?.articles_last_24h ?? "–"} in the last 24h`} icon={Newspaper} loading={isLoading} />
            <StatCard label="Model releases" value={data?.model_releases_7d} hint="Last 7 days" icon={Cpu} loading={isLoading} />
            <StatCard label="New GitHub issues" value={data?.new_github_issues_7d} hint="Last 7 days, tracked repos" icon={Bug} loading={isLoading} />
            <StatCard
              label="Critical CVEs"
              value={data?.critical_vulnerabilities_7d}
              hint={`Last 7 days · ${data?.known_exploited_7d ?? "–"} known exploited`}
              icon={ShieldAlert}
              tone="critical"
              loading={isLoading}
            />
            <StatCard
              label="Active incidents"
              value={data?.active_incidents}
              hint="Unresolved per provider status, verified < 2h"
              icon={Siren}
              tone={data?.active_incidents ? "critical" : "default"}
              loading={isLoading}
            />
          </div>

          {noData && (
            <EmptyState
              icon={Activity}
              title="No intelligence collected yet"
              description={
                <>
                  AI Pulse only shows real, sourced items. Collection connectors (RSS, GitHub, NVD, CISA KEV, arXiv,
                  status pages) are enabled in the next phase. {data.sources_enabled} source
                  {data.sources_enabled === 1 ? " is" : "s are"} configured.
                </>
              }
              action={
                <Button asChild variant="outline" size="sm">
                  <Link href="/analytics">View analytics</Link>
                </Button>
              }
            />
          )}

          <div className="grid gap-4 lg:grid-cols-3">
            <ChartCard
              className="lg:col-span-2"
              title="Activity"
              description="Items published per day, last 14 days"
              table={{ columns: ["Day", "Items"], rows: (data?.activity_14d ?? []).map((d) => [formatDay(d.day), d.count]) }}
            >
              {isLoading ? <Skeleton className="h-[220px]" /> : <ActivityChart data={data?.activity_14d ?? []} />}
            </ChartCard>
            <BriefingPreview />
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <ChartCard
              title="News distribution"
              description="Collected items by type"
              table={{ columns: ["Type", "Items"], rows: distribution.map((d) => [d.label, d.count]) }}
            >
              {isLoading ? (
                <Skeleton className="h-48" />
              ) : distribution.length ? (
                <DistributionChart data={distribution} />
              ) : (
                <p className="py-10 text-center text-sm text-muted-foreground">No items yet.</p>
              )}
            </ChartCard>
            <Card>
              <CardHeader>
                <CardTitle>Trending technologies</CardTitle>
              </CardHeader>
              <CardContent>
                {isLoading ? <Skeleton className="h-48" /> : <TrendingTags tags={data?.trending_tags ?? []} />}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Activity timeline</CardTitle>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <Skeleton className="h-48" />
                ) : !data?.latest.length ? (
                  <p className="py-10 text-center text-sm text-muted-foreground">Nothing collected yet.</p>
                ) : (
                  <ol className="relative space-y-4 border-l pl-4">
                    {data.latest.slice(0, 6).map((a) => (
                      <li key={a.id} className="relative">
                        <span className="absolute -left-[21px] top-1 size-2.5 rounded-full border-2 border-card bg-primary" />
                        <p className="text-[11px] text-muted-foreground">
                          {timeAgo(a.published_at ?? a.collected_at)} · {ITEM_TYPE_LABEL[a.item_type]}
                        </p>
                        <a
                          href={safeUrl(a.url)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="line-clamp-2 text-sm leading-snug hover:text-primary"
                        >
                          {a.title}
                        </a>
                      </li>
                    ))}
                  </ol>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <CompactArticleList title="Latest AI announcements" items={data?.latest_ai} loading={isLoading} href="/news" empty="No AI announcements yet." />
            <CompactArticleList title="Important security alerts" items={data?.top_security} loading={isLoading} href="/security" empty="No critical or high CVEs in the last 14 days." />
            <CompactArticleList title="Recent software failures" items={data?.recent_failures} loading={isLoading} href="/bugs" empty="No bugs or incidents in the last 14 days." />
          </div>
        </div>
      )}
    </>
  );
}
