"use client";

import { Bug, CheckCircle2, ShieldAlert, Siren, TriangleAlert } from "lucide-react";

import { ActivityChart, DistributionChart } from "@/components/charts/charts";
import { ChartCard } from "@/components/charts/chart-card";
import { StatCard } from "@/components/dashboard/stat-card";
import { Categories, Duration, Ext, KevBadge, Sev, StateBadge, Verified } from "@/components/radar/shared";
import { ErrorState, ListSkeleton } from "@/components/states/states";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SEVERITIES, SEVERITY_COLOR, SEVERITY_LABEL } from "@/lib/labels";
import { useRadar } from "@/lib/queries";
import type { Severity } from "@/lib/types";
import { formatDay, timeAgo } from "@/lib/utils";

function ListCard({ title, description, empty, children, count }: { title: string; description?: string; empty: string; children: React.ReactNode[]; count?: number }) {
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{title}{count != null && <span className="ml-1.5 text-muted-foreground">({count})</span>}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </div>
      </CardHeader>
      <CardContent>{children.length ? <ul className="divide-y">{children}</ul> : <p className="py-4 text-sm text-muted-foreground">{empty}</p>}</CardContent>
    </Card>
  );
}

export function RadarOverview() {
  const { data: d, isLoading, isError, error, refetch } = useRadar(30);
  if (isLoading) return <ListSkeleton rows={4} />;
  if (isError || !d) return <ErrorState error={error} onRetry={() => refetch()} />;

  const sevMap = new Map(d.severity_chart.map((r) => [r.key, r.count]));
  const sev = SEVERITIES.filter((s) => s !== "info").map((s: Severity) => ({ label: SEVERITY_LABEL[s], count: sevMap.get(s) ?? 0, color: SEVERITY_COLOR[s] }));
  const affected = d.most_affected.slice(0, 8).map((m) => ({ label: m.name, count: m.total }));
  const history = d.incident_history.map((h) => ({ day: h.day, count: h.total }));
  const thisWeek = d.weekly[d.weekly.length - 1];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-5">
        <StatCard label="Critical open bugs" value={d.critical_bugs.length} hint="Critical/high with a documented basis" icon={Bug} tone={d.critical_bugs.length ? "critical" : "default"} />
        <StatCard label="New critical/high CVEs" value={thisWeek?.critical_high_cves ?? 0} hint="Published this week" icon={ShieldAlert} />
        <StatCard label="Newly exploited" value={d.newly_exploited.length} hint="Added to CISA KEV, 7 days" icon={TriangleAlert} tone={d.newly_exploited.length ? "critical" : "default"} />
        <StatCard label="Active incidents" value={d.active_incidents.length} hint="Verified on the provider status page < 2 h" icon={Siren} tone={d.active_incidents.length ? "critical" : "default"} />
        <StatCard label="Unverified" value={d.unverified_incidents} hint="Unresolved in an old reading — not active" icon={CheckCircle2} />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <ListCard title="Active incidents" description="Unresolved per the provider and re-verified within 2 hours" empty="No verified active incidents right now." count={d.active_incidents.length}>
          {d.active_incidents.map((i) => (
            <li key={i.id} className="py-2.5 first:pt-0">
              <div className="flex items-start justify-between gap-3">
                <Ext href={i.status_page_url} className="text-sm font-medium">{i.provider}: {i.title}</Ext>
                <StateBadge i={i} />
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                <span>started {timeAgo(i.started_at)}</span>{i.impact && <span>· impact {i.impact}</span>}
                <span>· verified</span><Verified at={i.last_verified_at} />
              </div>
              <div className="mt-1"><Categories items={i.categories} /></div>
            </li>
          ))}
        </ListCard>
        <ListCard title="Resolved incidents (14 days)" empty="No resolved incidents in the last 14 days.">
          {d.resolved_incidents.map((i) => (
            <li key={i.id} className="flex items-start justify-between gap-3 py-2.5 first:pt-0">
              <div className="min-w-0">
                <Ext href={i.status_page_url} className="text-sm">{i.provider}: {i.title}</Ext>
                <p className="text-[11px] text-muted-foreground">resolved {timeAgo(i.resolved_at)} · duration <Duration minutes={i.duration_minutes} /></p>
              </div>
              <StateBadge i={i} />
            </li>
          ))}
        </ListCard>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <ListCard title="Critical bugs" description="Open, rated critical/high by the project's own labels" empty="No open critical bugs with a documented severity.">
          {d.critical_bugs.map((b) => (
            <li key={b.id} className="py-2.5 first:pt-0">
              <Ext href={b.source_url} className="text-sm font-medium">{b.title}</Ext>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                <Sev severity={b.severity} basis={b.severity_basis} />
                <span>{b.repository ?? b.project}{b.issue_number != null && ` #${b.issue_number}`}</span>
                {b.affected_versions.length > 0 && <span>· affects {b.affected_versions.join(", ")}</span>}
                <span>· opened {timeAgo(b.opened_at)}</span>
              </div>
            </li>
          ))}
        </ListCard>
        <ListCard title="Newly disclosed vulnerabilities (7 days)" description="Critical/high or known exploited" empty="No critical or high CVEs in the last 7 days.">
          {[...d.newly_exploited, ...d.new_vulnerabilities.filter((v) => !d.newly_exploited.some((k) => k.id === v.id))].slice(0, 10).map((v) => (
            <li key={v.id} className="py-2.5 first:pt-0">
              <div className="flex flex-wrap items-center gap-2">
                <Ext href={`https://nvd.nist.gov/vuln/detail/${v.cve_id}`} className="text-sm font-medium">{v.cve_id}</Ext>
                <Sev severity={v.severity} />
                {v.cvss_score != null && <span className="tabular text-xs text-muted-foreground">CVSS {v.cvss_score}</span>}
                {v.known_exploited && <KevBadge due={v.kev_due_date} />}
              </div>
              <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{v.description ?? v.remediation}</p>
            </li>
          ))}
        </ListCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Vulnerability severity" description={`CVEs published, last ${d.window_days} days`} table={{ columns: ["Severity", "CVEs"], rows: sev.map((s) => [s.label, s.count]) }}>
          <DistributionChart data={sev} colors={sev.map((s) => s.color)} unit="CVEs" />
        </ChartCard>
        <ChartCard title="Most affected technologies" description={`CVEs + bugs + incidents, last ${d.window_days} days`} table={{ columns: ["Technology", "Total"], rows: affected.map((a) => [a.label, a.count]) }}>
          {affected.length ? <DistributionChart data={affected} unit="items" /> : <p className="py-10 text-center text-sm text-muted-foreground">No data yet.</p>}
        </ChartCard>
      </div>

      <ChartCard title="Incident history" description={`Incidents started per day, last ${d.window_days} days`} table={{ columns: ["Day", "Incidents"], rows: history.map((h) => [formatDay(h.day), h.count]) }}>
        <ActivityChart data={history} height={200} />
      </ChartCard>

      <Card>
        <CardHeader><div><CardTitle>Weekly failure statistics</CardTitle><CardDescription>Last 8 weeks (ISO weeks starting Monday)</CardDescription></div></CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead><tr className="border-b text-left text-xs text-muted-foreground">
              {["Week", "Incidents", "Outage time", "Critical/high CVEs", "Added to KEV", "Bugs reported", "Bugs fixed"].map((h) => <th key={h} className="py-2 font-medium">{h}</th>)}
            </tr></thead>
            <tbody className="tabular">
              {[...d.weekly].reverse().map((w) => (
                <tr key={w.week_start} className="border-b last:border-0">
                  <td className="py-1.5">{formatDay(w.week_start)}</td><td>{w.incidents}</td>
                  <td><Duration minutes={w.outage_minutes} /></td><td>{w.critical_high_cves}</td><td>{w.kev_added}</td>
                  <td>{w.bugs_reported}</td><td>{w.bugs_fixed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
