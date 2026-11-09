"use client";

import { AlertTriangle, CheckCircle2, CircleSlash, Clock, DatabaseZap, ExternalLink, Play, RotateCcw, ShieldAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { StatCard } from "@/components/dashboard/stat-card";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState, ErrorState, ListSkeleton, SignInRequired } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/native-select";
import { Tooltip } from "@/components/ui/tooltip";
import { useAuth } from "@/lib/auth";
import { useIngestionActions, useIngestionStatus } from "@/lib/queries";
import type { SourceHealth, SourceStatus } from "@/lib/types";
import { cn, formatCount, formatDateTime, safeUrl, timeAgo } from "@/lib/utils";

const HEALTH: Record<SourceHealth, { label: string; className: string; icon: typeof CheckCircle2 }> = {
  healthy: { label: "Healthy", className: "text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/30", icon: CheckCircle2 },
  degraded: { label: "Degraded", className: "text-amber-700 dark:text-amber-300 bg-amber-500/10 border-amber-500/30", icon: AlertTriangle },
  stale: { label: "Stale", className: "text-amber-700 dark:text-amber-300 bg-amber-500/10 border-amber-500/30", icon: Clock },
  failing: { label: "Failing", className: "text-sev-critical bg-sev-critical/10 border-sev-critical/30", icon: ShieldAlert },
  never_run: { label: "Not run yet", className: "text-muted-foreground bg-muted border-border", icon: Clock },
  disabled: { label: "Disabled", className: "text-muted-foreground bg-muted border-border", icon: CircleSlash },
};
const INTERVALS = [10, 15, 30, 60, 120, 180, 360, 720, 1440];

function HealthBadge({ s }: { s: SourceStatus }) {
  const h = HEALTH[s.health];
  return (
    <Tooltip content={s.health_reason}>
      <span className={cn("inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-semibold", h.className)}>
        <h.icon className="size-3" /> {h.label}
      </span>
    </Tooltip>
  );
}

function Switch({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors disabled:opacity-50",
        checked ? "bg-primary" : "bg-muted-foreground/30",
      )}
    >
      <span className={cn("inline-block size-4 rounded-full bg-white shadow transition-transform", checked ? "translate-x-4.5" : "translate-x-0.5")} />
    </button>
  );
}

function LastRun({ s }: { s: SourceStatus }) {
  const j = s.last_job;
  if (!j) return <span className="text-muted-foreground">—</span>;
  return (
    <div className="text-xs">
      <span className={cn("font-medium", j.status === "failed" && "text-sev-critical", j.status === "partial" && "text-amber-600 dark:text-amber-300")}>
        {j.status}
      </span>{" "}
      <span className="text-muted-foreground">{timeAgo(j.started_at)}</span>
      <div className="tabular text-muted-foreground">
        +{j.items_created} new · {j.items_updated} upd
        {j.duration_seconds != null && ` · ${j.duration_seconds.toFixed(1)}s`}
      </div>
    </div>
  );
}

export default function IngestionPage() {
  const { user, status } = useAuth();
  const staff = !!user && (user.role === "admin" || user.role === "analyst");
  const q = useIngestionStatus(staff);
  const { run, retry, update } = useIngestionActions();
  const [filter, setFilter] = useState<SourceHealth | "all">("all");
  const sources = useMemo(
    () => (q.data?.sources ?? []).filter((s) => filter === "all" || s.health === filter),
    [q.data, filter],
  );
  const isAdmin = user?.role === "admin";

  if (status === "loading") return <ListSkeleton rows={3} />;
  if (status === "anonymous") return <SignInRequired what="ingestion dashboard" />;
  if (!staff)
    return <EmptyState icon={ShieldAlert} title="Admins and analysts only" description="Ask an administrator for access." />;

  const d = q.data;
  return (
    <>
      <PageHeader
        title="Ingestion"
        description="Health of every data source, recent runs and failures. Refreshes every 30 seconds."
        icon={DatabaseZap}
      />
      {q.isLoading ? (
        <ListSkeleton rows={4} />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : d ? (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
            <StatCard label="Enabled sources" value={d.totals.enabled} hint={`of ${d.totals.sources} configured`} icon={DatabaseZap} />
            <StatCard label="Healthy" value={d.by_health.healthy ?? 0} hint={`${(d.by_health.degraded ?? 0) + (d.by_health.stale ?? 0)} degraded or stale`} icon={CheckCircle2} />
            <StatCard label="Failing" value={d.by_health.failing ?? 0} hint="3+ consecutive failures" icon={ShieldAlert} tone={d.by_health.failing ? "critical" : "default"} />
            <StatCard label="Collected, last 24h" value={d.totals.items_24h} hint={`${formatCount(d.totals.items)} items in total`} icon={Clock} />
          </div>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Sources</CardTitle>
                <CardDescription>
                  {isAdmin ? "Enable, disable, change the polling interval or run a source now." : "Read-only for analysts, except Run now."}
                </CardDescription>
              </div>
              <NativeSelect aria-label="Filter by health" className="w-40" value={filter} onChange={(e) => setFilter(e.target.value as SourceHealth | "all")}>
                <option value="all">All ({d.sources.length})</option>
                {(Object.keys(HEALTH) as SourceHealth[]).map((h) => (
                  <option key={h} value={h}>
                    {HEALTH[h].label} ({d.by_health[h] ?? 0})
                  </option>
                ))}
              </NativeSelect>
            </CardHeader>
            <CardContent className="px-0 sm:px-5">
              {!sources.length ? (
                <p className="px-5 py-8 text-center text-sm text-muted-foreground">No sources match.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[920px] text-sm">
                    <thead>
                      <tr className="border-b text-left text-xs text-muted-foreground">
                        <th className="px-5 py-2 font-medium sm:px-0">Source</th>
                        <th className="py-2 font-medium">Health</th>
                        <th className="py-2 font-medium">Last success</th>
                        <th className="py-2 font-medium">Last run</th>
                        <th className="py-2 text-right font-medium">Items 24h / total</th>
                        <th className="py-2 pl-4 font-medium">Every</th>
                        <th className="py-2 font-medium">On</th>
                        <th className="py-2" />
                      </tr>
                    </thead>
                    <tbody>
                      {sources.map((s) => (
                        <tr key={s.id} className="border-b align-top last:border-0">
                          <td className="max-w-[300px] px-5 py-3 sm:px-0">
                            <a href={safeUrl(s.url)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-medium hover:text-primary">
                              {s.name} <ExternalLink className="size-3 shrink-0 opacity-60" />
                            </a>
                            <div className="mt-0.5 flex flex-wrap gap-1.5 text-[11px] text-muted-foreground">
                              <Badge variant="outline">{s.connector}</Badge>
                              {s.is_official && <Badge variant="outline">official</Badge>}
                            </div>
                            {s.last_error && s.health !== "healthy" && (
                              <p className="mt-1 line-clamp-2 text-[11px] text-sev-critical" title={s.last_error}>
                                {s.last_error}
                              </p>
                            )}
                          </td>
                          <td className="py-3">
                            <HealthBadge s={s} />
                          </td>
                          <td className="py-3 text-xs">
                            {s.last_success_at ? (
                              <Tooltip content={formatDateTime(s.last_success_at)}>
                                <span>{timeAgo(s.last_success_at)}</span>
                              </Tooltip>
                            ) : (
                              <span className="text-muted-foreground">never</span>
                            )}
                            {s.next_run_at && <div className="text-muted-foreground">next {timeAgo(s.next_run_at).replace(" ago", "")}</div>}
                          </td>
                          <td className="py-3">
                            <LastRun s={s} />
                          </td>
                          <td className="tabular py-3 text-right text-xs">
                            {formatCount(s.items_24h)} / {formatCount(s.items_total)}
                          </td>
                          <td className="py-3 pl-4">
                            <NativeSelect
                              aria-label={`Polling interval for ${s.name}`}
                              className="w-24"
                              value={s.poll_interval_minutes}
                              disabled={!isAdmin || update.isPending}
                              onChange={(e) => update.mutate({ id: s.id, patch: { poll_interval_minutes: Number(e.target.value) } })}
                            >
                              {[...new Set([...INTERVALS, s.poll_interval_minutes])].sort((a, b) => a - b).map((m) => (
                                <option key={m} value={m}>
                                  {m < 60 ? `${m} min` : `${m / 60} h`}
                                </option>
                              ))}
                            </NativeSelect>
                          </td>
                          <td className="py-3">
                            <Switch
                              checked={s.enabled}
                              label={`${s.enabled ? "Disable" : "Enable"} ${s.name}`}
                              disabled={!isAdmin || update.isPending}
                              onChange={(v) => update.mutate({ id: s.id, patch: { enabled: v } })}
                            />
                          </td>
                          <td className="py-3 pr-1 text-right">
                            <Button size="sm" variant="outline" disabled={run.isPending} onClick={() => run.mutate(s.id)} aria-label={`Run ${s.name} now`}>
                              <Play /> Run
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Recent failed jobs</CardTitle>
                <CardDescription>Failed runs are retried automatically with exponential backoff; you can also retry manually.</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {!d.recent_failures.length ? (
                <p className="text-sm text-muted-foreground">No failed jobs. 🎉</p>
              ) : (
                <ul className="divide-y">
                  {d.recent_failures.map((j) => {
                    const src = d.sources.find((s) => s.id === j.source_id);
                    return (
                      <li key={j.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0">
                          <p className="text-sm font-medium">
                            {src?.name ?? j.source_id}{" "}
                            <span className="text-xs font-normal text-muted-foreground">
                              · {timeAgo(j.started_at)} · attempt {j.attempt} · {j.trigger}
                            </span>
                          </p>
                          <p className="mt-0.5 break-words text-xs text-sev-critical">{j.error}</p>
                        </div>
                        <Button size="sm" variant="outline" className="shrink-0" disabled={retry.isPending} onClick={() => retry.mutate(j.id)}>
                          <RotateCcw /> Retry
                        </Button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}
    </>
  );
}
