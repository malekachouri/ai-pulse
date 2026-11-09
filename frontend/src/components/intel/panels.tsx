"use client";

import { ArrowUpRight, Clock, Cpu, ExternalLink, ShieldAlert, Siren, Star, TrendingUp } from "lucide-react";

import { ErrorState } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip } from "@/components/ui/tooltip";
import { SEVERITY_COLOR, SEVERITY_LABEL } from "@/lib/labels";
import { useIncidents, useModels, useRisingRepos, useSecurityStats } from "@/lib/queries";
import type { Incident, Severity } from "@/lib/types";
import { formatCount, formatDateTime, safeUrl, timeAgo, titleCase } from "@/lib/utils";

function PanelSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-10" />
      <Skeleton className="h-10" />
    </div>
  );
}

function IncidentRow({ i }: { i: Incident }) {
  const href = safeUrl(i.status_page_url);
  return (
    <li className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{i.provider}</span>
          <Badge variant="outline">{titleCase(i.status)}</Badge>
          {i.impact && <Badge variant="secondary">Impact: {i.impact}</Badge>}
        </div>
        <p className="mt-1 text-sm font-medium leading-snug">{i.title}</p>
        {i.affected_services.length > 0 && (
          <p className="mt-0.5 text-xs text-muted-foreground">Affects: {i.affected_services.join(", ")}</p>
        )}
      </div>
      <div className="flex shrink-0 flex-col items-start gap-1 text-xs text-muted-foreground sm:items-end">
        <span>Started {timeAgo(i.started_at)}</span>
        <Tooltip content={`Status last checked on the provider's status page: ${formatDateTime(i.last_verified_at)}`}>
          <span className="inline-flex items-center gap-1">
            <Clock className="size-3" /> verified {timeAgo(i.last_verified_at)}
          </span>
        </Tooltip>
        {href && (
          <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
            Official status <ExternalLink className="size-3" />
          </a>
        )}
      </div>
    </li>
  );
}

/** Only incidents the provider reports as unresolved AND that were re-verified recently. */
export function ActiveIncidentsPanel() {
  const q = useIncidents({ active_only: true, page_size: 10, sort: "-started_at" });
  return (
    <Card className="mb-5">
      <CardHeader>
        <div>
          <CardTitle className="flex items-center gap-2">
            <Siren className="size-4 text-sev-critical" /> Active incidents
          </CardTitle>
          <CardDescription>
            Unresolved per the provider&apos;s own status page and verified within the last 2 hours.
          </CardDescription>
        </div>
        {q.data && q.data.total > 0 && <Badge variant="secondary">{q.data.total}</Badge>}
      </CardHeader>
      <CardContent>
        {q.isLoading ? (
          <PanelSkeleton />
        ) : q.isError ? (
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        ) : !q.data?.items.length ? (
          <p className="text-sm text-muted-foreground">No verified active incidents right now.</p>
        ) : (
          <ul className="divide-y">
            {q.data.items.map((i) => (
              <IncidentRow key={i.id} i={i} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function SecurityStatsStrip() {
  const q = useSecurityStats();
  if (q.isError) return null;
  const s = q.data;
  const order: Severity[] = ["critical", "high", "medium", "low"];
  return (
    <Card className="mb-5">
      <CardContent className="grid grid-cols-2 gap-4 pt-5 sm:grid-cols-4">
        <div>
          <p className="text-xs text-muted-foreground">Tracked CVEs</p>
          {s ? <p className="text-2xl font-semibold">{formatCount(s.total)}</p> : <Skeleton className="mt-1 h-7 w-12" />}
        </div>
        <div>
          <p className="flex items-center gap-1 text-xs text-muted-foreground">
            <ShieldAlert className="size-3.5 text-sev-critical" /> Known exploited (CISA KEV)
          </p>
          {s ? <p className="text-2xl font-semibold">{formatCount(s.known_exploited)}</p> : <Skeleton className="mt-1 h-7 w-12" />}
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Published, last 7 days</p>
          {s ? (
            <p className="text-2xl font-semibold">
              {formatCount(s.published_last_7d)}{" "}
              <span className="text-sm font-normal text-muted-foreground">({s.critical_last_7d} critical)</span>
            </p>
          ) : (
            <Skeleton className="mt-1 h-7 w-12" />
          )}
        </div>
        <div>
          <p className="text-xs text-muted-foreground">By severity</p>
          {s ? (
            <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs">
              {order.map((sev) => (
                <li key={sev} className="inline-flex items-center gap-1">
                  <span className="size-2 rounded-full" style={{ backgroundColor: SEVERITY_COLOR[sev] }} aria-hidden />
                  {SEVERITY_LABEL[sev]} <span className="tabular font-semibold">{s.by_severity[sev] ?? 0}</span>
                </li>
              ))}
            </ul>
          ) : (
            <Skeleton className="mt-1 h-5 w-full" />
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function RisingReposPanel() {
  const q = useRisingRepos();
  return (
    <Card className="mb-5">
      <CardHeader>
        <div>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="size-4 text-primary" /> Fastest-rising repositories
          </CardTitle>
          <CardDescription>
            Stars gained over 7 days, measured from AI Pulse&apos;s own snapshots (GitHub has no trending API).
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        {q.isLoading ? (
          <PanelSkeleton />
        ) : q.isError ? (
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        ) : !q.data?.items.length ? (
          <p className="text-sm text-muted-foreground">No repositories tracked yet.</p>
        ) : (
          <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {q.data.items.map((r) => (
              <li key={r.id} className="rounded-lg border p-3">
                <a
                  href={safeUrl(r.html_url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm font-medium hover:text-primary"
                >
                  {r.full_name} <ArrowUpRight className="size-3" />
                </a>
                {r.description && <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{r.description}</p>}
                <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <Star className="size-3" /> {formatCount(r.stars)}
                  </span>
                  <span className="tabular font-semibold text-foreground">
                    {r.stars_delta_7d == null ? "Δ n/a" : `+${formatCount(r.stars_delta_7d)} / 7d`}
                  </span>
                  {r.language && <span>{r.language}</span>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function ModelsPanel() {
  const q = useModels();
  return (
    <Card className="mb-5">
      <CardHeader>
        <div>
          <CardTitle className="flex items-center gap-2">
            <Cpu className="size-4 text-primary" /> Tracked models
          </CardTitle>
          <CardDescription>Latest known release per model, linked to the vendor&apos;s announcement.</CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        {q.isLoading ? (
          <PanelSkeleton />
        ) : q.isError ? (
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        ) : !q.data?.items.length ? (
          <p className="text-sm text-muted-foreground">No models tracked yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="py-2 font-medium">Model</th>
                  <th className="py-2 font-medium">Provider</th>
                  <th className="py-2 font-medium">Weights</th>
                  <th className="py-2 font-medium">Latest release</th>
                </tr>
              </thead>
              <tbody>
                {q.data.items.map((m) => {
                  const rel = m.latest_release;
                  return (
                    <tr key={m.id} className="border-b last:border-0">
                      <td className="py-2 font-medium">{m.name}</td>
                      <td className="py-2 text-muted-foreground">{m.provider}</td>
                      <td className="py-2">
                        {m.is_open_weights == null ? "Unknown" : m.is_open_weights ? "Open" : "Closed"}
                      </td>
                      <td className="py-2">
                        {rel ? (
                          <a href={safeUrl(rel.source_url)} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                            {rel.version ?? "Release"} · {timeAgo(rel.released_at)}
                          </a>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
