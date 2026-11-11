"use client";

import { Activity, Bell, Bookmark, Cpu, Database, Gauge, Users } from "lucide-react";
import { useState } from "react";

import { HealthPill, StaffGate, useIsStaff } from "@/components/admin/admin-shell";
import { ActivityChart } from "@/components/charts/charts";
import { ChartCard } from "@/components/charts/chart-card";
import { StatCard } from "@/components/dashboard/stat-card";
import { PageHeader } from "@/components/layout/page-header";
import { ErrorState, ListSkeleton } from "@/components/states/states";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/native-select";
import { useSystemHealth, useUsageStats } from "@/lib/queries";
import type { DayValue, HealthCheck } from "@/lib/types";
import { formatCount, formatDateTime, formatDay, titleCase } from "@/lib/utils";

const CHECK_LABEL: Record<string, string> = {
  database: "PostgreSQL",
  migrations: "Schema migrations",
  redis: "Redis & queues",
  scheduler: "Scheduler (Celery Beat)",
  workers: "Workers (Celery)",
  ingestion: "Ingestion",
  ai_provider: "AI provider",
};

function fmtValue(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") return v.toLocaleString("en");
  if (typeof v === "string") return /^\d{4}-\d{2}-\d{2}T/.test(v) ? formatDateTime(v) : v;
  if (Array.isArray(v)) return v.length ? v.join(", ") : "none";
  return Object.entries(v as Record<string, unknown>)
    .map(([k, x]) => `${k}: ${typeof x === "object" && x ? Object.values(x).join("/") : String(x)}`)
    .join(" · ");
}

function CheckCard({ c }: { c: HealthCheck }) {
  const data = Object.entries(c.data).filter(([k]) => k !== "size_bytes");
  // min-w-0: grid and flex children default to min-width:auto, so one long value (a version string,
  // an error) would widen the whole card and the page on phones instead of being truncated.
  return (
    <Card className="min-w-0">
      <CardContent className="space-y-2 pt-5 text-sm">
        <div className="flex items-center justify-between gap-2">
          <p className="font-medium">{CHECK_LABEL[c.name] ?? titleCase(c.name)}</p>
          <HealthPill status={c.status} />
        </div>
        {c.detail && <p className="break-words text-xs text-muted-foreground">{c.detail}</p>}
        <dl className="space-y-0.5 text-xs">
          {c.latency_ms != null && (
            <div className="flex justify-between gap-3">
              <dt className="text-muted-foreground">Latency</dt>
              <dd className="tabular">{c.latency_ms} ms</dd>
            </div>
          )}
          {c.name === "database" && typeof c.data.size_bytes === "number" && (
            <div className="flex justify-between gap-3">
              <dt className="text-muted-foreground">Size</dt>
              <dd className="tabular">{(c.data.size_bytes / 1024 / 1024).toFixed(1)} MB</dd>
            </div>
          )}
          {data.map(([k, v]) => (
            <div key={k} className="flex justify-between gap-3">
              <dt className="shrink-0 text-muted-foreground">{titleCase(k.replace(/_/g, " "))}</dt>
              <dd className="tabular min-w-0 truncate text-right" title={fmtValue(v)}>
                {fmtValue(v)}
              </dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

function Series({ title, description, data, unit }: { title: string; description: string; data: DayValue[]; unit: string }) {
  return (
    <ChartCard
      title={title}
      description={description}
      table={{ columns: ["Day", titleCase(unit)], rows: data.map((d) => [formatDay(d.day), d.value]) }}
    >
      <ActivityChart data={data.map((d) => ({ day: d.day, count: d.value }))} unit={unit} label={`${title} per day`} height={180} />
    </ChartCard>
  );
}

function Overview() {
  const { staff } = useIsStaff();
  const [days, setDays] = useState(30);
  const health = useSystemHealth(staff);
  const usage = useUsageStats(staff, days);
  const u = usage.data;
  return (
    <div className="space-y-6">
      <section aria-labelledby="sys">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 id="sys" className="flex items-center gap-2 text-base font-semibold">
            System health {health.data && <HealthPill status={health.data.status} />}
          </h2>
          {health.data && (
            <p className="text-xs text-muted-foreground">
              {health.data.environment} · v{health.data.version} · up since {formatDateTime(health.data.started_at)} · checked{" "}
              {formatDateTime(health.data.checked_at)} (refreshes every 30 s)
            </p>
          )}
        </div>
        {health.isLoading ? (
          <ListSkeleton rows={2} />
        ) : health.isError ? (
          <ErrorState error={health.error} onRetry={() => health.refetch()} />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {health.data?.checks.map((c) => <CheckCard key={c.name} c={c} />)}
          </div>
        )}
      </section>

      <section aria-labelledby="usage" className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="usage" className="text-base font-semibold">
            Usage
          </h2>
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Window</span>
            <NativeSelect value={days} onChange={(e) => setDays(Number(e.target.value))} className="w-32">
              {[7, 30, 90].map((d) => (
                <option key={d} value={d}>
                  {d} days
                </option>
              ))}
            </NativeSelect>
          </label>
        </div>
        {usage.isLoading ? (
          <ListSkeleton rows={2} />
        ) : usage.isError ? (
          <ErrorState error={usage.error} onRetry={() => usage.refetch()} />
        ) : u ? (
          <>
            <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
              <StatCard label="Users" value={u.users_total} hint={`${u.users_new} new · ${u.users_logged_in_7d} signed in this week`} icon={Users} />
              <StatCard label="Collected items" value={u.articles_total} hint={`${formatCount(u.articles_by_day.reduce((a, d) => a + d.value, 0))} in ${days} days`} icon={Database} />
              <StatCard
                label="AI tokens"
                value={u.ai_tokens_total}
                hint={u.ai_cost_total_usd != null ? `≈ $${u.ai_cost_total_usd.toFixed(2)} in ${days} days` : "no pricing configured"}
                icon={Cpu}
              />
              <StatCard
                label="Notifications"
                value={Object.values(u.notifications_by_kind).reduce((a, b) => a + b, 0)}
                hint={u.notifications_read_ratio != null ? `${Math.round(u.notifications_read_ratio * 100)}% read · ${u.bookmarks_total} bookmarks` : `${u.bookmarks_total} bookmarks`}
                icon={Bell}
              />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <Series title="Collected items" description="New items stored per day (all sources)" data={u.articles_by_day} unit="items" />
              <Series
                title="AI tokens"
                description="Input + output tokens per day, all providers"
                data={u.ai_by_day.map((d) => ({ day: d.day, value: d.tokens }))}
                unit="tokens"
              />
              <Series title="Notifications delivered" description="In-app notifications created per day" data={u.notifications_by_day} unit="notifications" />
              <Series title="Sign-ups" description="New accounts per day" data={u.signups_by_day} unit="accounts" />
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <Card>
                <CardHeader>
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Users className="size-4 text-primary" /> Users by role
                    </CardTitle>
                    <CardDescription>{u.users_active} active accounts</CardDescription>
                  </div>
                </CardHeader>
                <CardContent>
                  <KeyValues data={u.users_by_role} />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Activity className="size-4 text-primary" /> Items by type
                    </CardTitle>
                    <CardDescription>All time</CardDescription>
                  </div>
                </CardHeader>
                <CardContent>
                  <KeyValues data={u.articles_by_type} />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Bookmark className="size-4 text-primary" /> Notifications by kind
                    </CardTitle>
                    <CardDescription>Last {days} days</CardDescription>
                  </div>
                </CardHeader>
                <CardContent>
                  <KeyValues data={u.notifications_by_kind} />
                </CardContent>
              </Card>
            </div>
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <Gauge className="size-3.5" /> Latency, error rates, queue length and alerting live in Grafana (see docs/DEPLOYMENT.md, Monitoring).
            </p>
          </>
        ) : null}
      </section>
    </div>
  );
}

function KeyValues({ data }: { data: Record<string, number | undefined> }) {
  const rows = Object.entries(data).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0));
  if (!rows.length) return <p className="text-sm text-muted-foreground">No data yet.</p>;
  return (
    <dl className="space-y-1 text-sm">
      {rows.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-3">
          <dt className="text-muted-foreground">{titleCase(k.replace(/_/g, " "))}</dt>
          <dd className="tabular font-medium">{(v ?? 0).toLocaleString("en")}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function AdminOverviewPage() {
  return (
    <>
      <PageHeader
        title="Administration"
        description="System health, usage and operations. Every change made here is recorded in the audit log."
        icon={Gauge}
      />
      <StaffGate what="administration">
        <Overview />
      </StaffGate>
    </>
  );
}
