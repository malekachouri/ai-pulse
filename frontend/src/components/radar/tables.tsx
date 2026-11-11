"use client";

import { GitPullRequest } from "lucide-react";
import { useState } from "react";

import { Pagination } from "@/components/feed/pagination";
import { BugIntelligenceButton } from "@/components/intel/bug-intelligence";
import { Categories, Duration, Ext, KevBadge, Sev, StateBadge, Td, Th, Verified } from "@/components/radar/shared";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/native-select";
import { useBugList, useIncidentList, useVulnList } from "@/lib/queries";
import { formatDateTime, safeUrl, timeAgo, titleCase } from "@/lib/utils";

/** One line per vendor/product (KEV and NVD often describe the same product twice). */
function uniqueProducts(items: { vendor?: string; product?: string; ecosystem?: string; vulnerable_range?: string; version?: string }[]): string[] {
  const seen = new Map<string, string>();
  for (const p of items) {
    const key = `${(p.vendor ?? p.ecosystem ?? "").toLowerCase().replace(/[^a-z0-9]/g, "")}/${(p.product ?? "").toLowerCase().replace(/[^a-z0-9]/g, "")}`;
    const label = [p.vendor ?? p.ecosystem, p.product].filter(Boolean).join(" / ") + (p.vulnerable_range ? ` (${p.vulnerable_range})` : p.version ? ` ${p.version}` : "");
    if (!seen.has(key) || label.length > (seen.get(key) ?? "").length) seen.set(key, label);
  }
  return [...seen.values()];
}

const hostOf = (u: string) => { const s = safeUrl(u); return s ? new URL(s).hostname : "link"; };

function Filters({ children }: { children: React.ReactNode }) {
  return <div className="mb-3 flex flex-wrap gap-2">{children}</div>;
}

function Shell({ q, empty, children, page, setPage }: {
  q: { isLoading: boolean; isError: boolean; error: unknown; refetch: () => void; data?: { items: unknown[]; total: number; page: number; pages: number; page_size: number } };
  empty: string; children: React.ReactNode; page: number; setPage: (n: number) => void;
}) {
  if (q.isLoading) return <ListSkeleton rows={3} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={q.refetch} />;
  if (!q.data?.items.length) return <EmptyState title={empty} description="Nothing matches these filters in the collected data." />;
  return (
    <>
      <Card><CardContent className="overflow-x-auto rounded-xl p-0 outline-none focus-visible:ring-2 focus-visible:ring-ring" tabIndex={0} role="region" aria-label="Results table">{children}</CardContent></Card>
      <Pagination page={page} pages={q.data.pages} total={q.data.total} pageSize={q.data.page_size} onChange={setPage} />
    </>
  );
}

export function BugsTable() {
  const [page, setPage] = useState(1);
  const [view, setView] = useState("open");
  const [kind, setKind] = useState("");
  const params: Record<string, string | number | string[] | undefined> = {
    page, page_size: 20, sort: view === "critical" ? "-severity" : "-created_at", kind: kind || undefined,
    ...(view === "open" ? { status: "open" } : view === "critical" ? { status: "open", severity: ["critical", "high"] }
      : view === "new" ? { reported_within_days: 7 } : view === "fixed" ? { resolution: "fixed" } : {}),
  };
  const q = useBugList(params);
  return (
    <section>
      <Filters>
        <NativeSelect aria-label="Bug view" className="w-52" value={view} onChange={(e) => { setView(e.target.value); setPage(1); }}>
          <option value="open">Open bugs</option>
          <option value="critical">Critical / high (open)</option>
          <option value="new">Newly reported (7 days)</option>
          <option value="fixed">Fixed (linked fix)</option>
          <option value="all">All</option>
        </NativeSelect>
        <NativeSelect aria-label="Bug kind" className="w-44" value={kind} onChange={(e) => { setKind(e.target.value); setPage(1); }}>
          <option value="">All kinds</option>
          {["bug", "regression", "performance", "compatibility", "security"].map((k) => <option key={k} value={k}>{titleCase(k)}</option>)}
        </NativeSelect>
      </Filters>
      <Shell q={q} empty="No bugs collected" page={page} setPage={setPage}>
        <table className="w-full min-w-[1100px]">
          <thead className="border-b"><tr><Th>Bug</Th><Th>Status</Th><Th>Severity</Th><Th>Labels</Th><Th>Created</Th><Th>Updated</Th><Th>Affected</Th><Th>Fix</Th><Th>Verified</Th></tr></thead>
          <tbody className="divide-y">
            {q.data?.items.map((b) => (
              <tr key={b.id}>
                <Td className="max-w-[320px]">
                  <Ext href={b.source_url} className="font-medium">{b.title}</Ext>
                  <p className="mt-0.5 text-xs text-muted-foreground">{b.repository ?? b.project}{b.issue_number != null && ` #${b.issue_number}`} · {titleCase(b.kind)}</p>
                  <BugIntelligenceButton articleId={b.article_id} label={b.title} />
                </Td>
                <Td><Badge variant={b.status === "open" ? "default" : "secondary"}>{b.status}</Badge>{b.resolution && <p className="mt-1 text-[11px] text-muted-foreground">{titleCase(b.resolution)}</p>}</Td>
                <Td><Sev severity={b.severity} basis={b.severity_basis} /></Td>
                <Td className="max-w-[180px]"><div className="flex flex-wrap gap-1">{b.labels.slice(0, 5).map((l) => <Badge key={l} variant="outline">{l}</Badge>)}</div></Td>
                <Td className="whitespace-nowrap text-xs">{b.opened_at ? timeAgo(b.opened_at) : "—"}</Td>
                <Td className="whitespace-nowrap text-xs">{b.source_updated_at ? timeAgo(b.source_updated_at) : "—"}</Td>
                <Td className="text-xs">{b.affected_versions.length ? b.affected_versions.join(", ") : <span className="text-muted-foreground">Not stated</span>}</Td>
                <Td className="text-xs">{b.fix_url ? <Ext href={b.fix_url}><GitPullRequest className="size-3" /> {b.fix_url.includes("/pull/") ? "PR" : "Commit"}</Ext> : <span className="text-muted-foreground">None linked</span>}</Td>
                <Td className="text-xs"><Verified at={b.last_verified_at} /></Td>
              </tr>
            ))}
          </tbody>
        </table>
      </Shell>
    </section>
  );
}

export function IncidentsTable() {
  const [page, setPage] = useState(1);
  const [state, setState] = useState("current");
  const [category, setCategory] = useState("");
  const q = useIncidentList({ page, page_size: 20, state: state || undefined, category: category ? [category] : undefined, sort: "-started_at" });
  return (
    <section>
      <Filters>
        <NativeSelect aria-label="Incident state" className="w-56" value={state} onChange={(e) => { setState(e.target.value); setPage(1); }}>
          <option value="current">Current (verified active)</option>
          <option value="historical">Historical (resolved)</option>
          <option value="unverified">Unverified (stale reading)</option>
          <option value="">All</option>
        </NativeSelect>
        <NativeSelect aria-label="Incident category" className="w-48" value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }}>
          <option value="">All categories</option>
          {[["cloud", "Cloud outages"], ["infrastructure", "Infrastructure"], ["api", "API failures"], ["database", "Databases"],
            ["ai_provider", "AI providers"], ["kubernetes_docker", "Kubernetes & Docker"], ["developer_platform", "Developer platforms"]]
            .map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </NativeSelect>
      </Filters>
      <Shell q={q} empty={state === "current" ? "No verified active incidents right now" : "No incidents"} page={page} setPage={setPage}>
        <table className="w-full min-w-[1000px]">
          <thead className="border-b"><tr><Th>Incident</Th><Th>State</Th><Th>Provider status</Th><Th>Impact</Th><Th>Started</Th><Th>Resolved</Th><Th>Duration</Th><Th>Verified</Th></tr></thead>
          <tbody className="divide-y">
            {q.data?.items.map((i) => (
              <tr key={i.id}>
                <Td className="max-w-[360px]">
                  <Ext href={i.status_page_url} className="font-medium">{i.provider}: {i.title}</Ext>
                  {i.affected_services.length > 0 && <p className="mt-0.5 text-xs text-muted-foreground">Services: {i.affected_services.slice(0, 4).join(", ")}</p>}
                  <div className="mt-1"><Categories items={i.categories} /></div>
                </Td>
                <Td><StateBadge i={i} /></Td>
                <Td className="text-xs">{titleCase(i.status)}</Td>
                <Td className="text-xs">{i.impact ?? <span className="text-muted-foreground">Not stated</span>}</Td>
                <Td className="whitespace-nowrap text-xs">{formatDateTime(i.started_at)}</Td>
                <Td className="whitespace-nowrap text-xs">{i.resolved_at ? formatDateTime(i.resolved_at) : "—"}</Td>
                <Td className="text-xs"><Duration minutes={i.duration_minutes} /></Td>
                <Td className="text-xs"><Verified at={i.last_verified_at} /></Td>
              </tr>
            ))}
          </tbody>
        </table>
      </Shell>
    </section>
  );
}

export function VulnsTable() {
  const [page, setPage] = useState(1);
  const [sev, setSev] = useState("");
  const [kev, setKev] = useState("");
  const [patch, setPatch] = useState("");
  const q = useVulnList({
    page, page_size: 20, sort: "-published_at", severity: sev ? sev.split(",") : undefined,
    known_exploited: kev === "" ? undefined : kev === "yes", patch_available: patch === "" ? undefined : patch === "yes",
  });
  return (
    <section>
      <Filters>
        <NativeSelect aria-label="Severity" className="w-44" value={sev} onChange={(e) => { setSev(e.target.value); setPage(1); }}>
          <option value="critical,high">Critical & high</option>
          <option value="critical">Critical</option>
          <option value="medium,low">Medium & low</option>
          <option value="">Any severity</option>
        </NativeSelect>
        <NativeSelect aria-label="Exploitation" className="w-48" value={kev} onChange={(e) => { setKev(e.target.value); setPage(1); }}>
          <option value="">Any exploitation status</option>
          <option value="yes">Known exploited (KEV)</option>
          <option value="no">No known exploitation</option>
        </NativeSelect>
        <NativeSelect aria-label="Patch" className="w-40" value={patch} onChange={(e) => { setPatch(e.target.value); setPage(1); }}>
          <option value="">Any patch status</option>
          <option value="yes">Patch available</option>
        </NativeSelect>
      </Filters>
      <Shell q={q} empty="No vulnerabilities match" page={page} setPage={setPage}>
        <table className="w-full min-w-[1150px]">
          <thead className="border-b"><tr><Th>CVE</Th><Th>CVSS</Th><Th>Severity</Th><Th>Affected software</Th><Th>Exploited</Th><Th>Published</Th><Th>Patch</Th><Th>Mitigation</Th><Th>References</Th><Th>Verified</Th></tr></thead>
          <tbody className="divide-y">
            {q.data?.items.map((v) => (
              <tr key={v.id}>
                <Td className="whitespace-nowrap font-medium">
                  <Ext href={`https://nvd.nist.gov/vuln/detail/${v.cve_id}`}>{v.cve_id}</Ext>
                  <div><BugIntelligenceButton articleId={v.article_id} label={v.cve_id} /></div>
                </Td>
                <Td className="tabular text-xs">{v.cvss_score != null ? <span title={v.cvss_vector ?? ""}>{v.cvss_score} <span className="text-muted-foreground">v{v.cvss_version}</span></span> : <span className="text-muted-foreground">Not published</span>}</Td>
                <Td><Sev severity={v.severity} /></Td>
                <Td className="max-w-[220px] text-xs">
                  {uniqueProducts(v.affected_products).slice(0, 3).map((label) => <p key={label}>{label}</p>)}
                  {uniqueProducts(v.affected_products).length > 3 && <p className="text-muted-foreground">+{uniqueProducts(v.affected_products).length - 3} more</p>}
                  {!v.affected_products.length && <span className="text-muted-foreground">Not stated</span>}
                </Td>
                <Td>{v.known_exploited ? <KevBadge due={v.kev_due_date} /> : <span className="text-xs text-muted-foreground">None reported</span>}</Td>
                <Td className="whitespace-nowrap text-xs">{v.published_at ? timeAgo(v.published_at) : "—"}</Td>
                <Td className="text-xs">{v.patch_available ? "Available" : <span className="text-muted-foreground">Unknown</span>}</Td>
                <Td className="max-w-[240px] text-xs">{v.remediation ? <span className="line-clamp-3" title={v.remediation}>{v.remediation}</span> : <span className="text-muted-foreground">No official mitigation published</span>}</Td>
                <Td className="text-xs">{v.references.slice(0, 2).map((r) => <p key={r.url}><Ext href={r.url}>{hostOf(r.url)}</Ext></p>)}{v.references.length > 2 && <p className="text-muted-foreground">+{v.references.length - 2}</p>}</Td>
                <Td className="text-xs"><Verified at={v.last_verified_at} /></Td>
              </tr>
            ))}
          </tbody>
        </table>
      </Shell>
    </section>
  );
}
