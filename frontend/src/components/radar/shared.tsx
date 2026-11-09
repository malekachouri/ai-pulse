"use client";

import { Clock, ExternalLink, ShieldAlert } from "lucide-react";

import { SeverityBadge } from "@/components/feed/badges";
import { Badge } from "@/components/ui/badge";
import { Tooltip } from "@/components/ui/tooltip";
import type { RadarIncident, Severity } from "@/lib/types";
import { cn, formatDateTime, safeUrl, timeAgo, titleCase } from "@/lib/utils";

export function Ext({ href, children, className }: { href: string | null | undefined; children: React.ReactNode; className?: string }) {
  const url = safeUrl(href);
  if (!url) return <span className={className}>{children}</span>;
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className={cn("inline-flex items-center gap-1 hover:text-primary hover:underline", className)}>
      {children} <ExternalLink className="size-3 shrink-0 opacity-60" />
    </a>
  );
}

export function Verified({ at }: { at: string | null | undefined }) {
  if (!at) return <span className="text-muted-foreground">—</span>;
  return (
    <Tooltip content={`Last read from the official source: ${formatDateTime(at)}`}>
      <span className="inline-flex items-center gap-1 text-muted-foreground"><Clock className="size-3" /> {timeAgo(at)}</span>
    </Tooltip>
  );
}

/** Severity with its basis; "Not rated" when no documented basis exists. */
export function Sev({ severity, basis }: { severity: Severity; basis?: string | null }) {
  if (severity === "unknown" || (!basis && basis !== undefined)) return <span className="text-xs text-muted-foreground">Not rated</span>;
  return <SeverityBadge severity={severity} basis={basis ?? undefined} />;
}

export function StateBadge({ i }: { i: Pick<RadarIncident, "state"> }) {
  const map = {
    current: { label: "Active", cls: "border-sev-critical/40 bg-sev-critical/10 text-sev-critical" },
    historical: { label: "Resolved", cls: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" },
    unverified: { label: "Unverified", cls: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300" },
  }[i.state];
  const hint = i.state === "unverified"
    ? "Not resolved in the last reading, but the provider's status wasn't re-confirmed recently — not shown as active."
    : i.state === "current" ? "Unresolved on the provider's status page, verified within the last 2 hours." : "Resolved per the provider.";
  return (
    <Tooltip content={hint}>
      <span className={cn("inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold", map.cls)}>{map.label}</span>
    </Tooltip>
  );
}

export function Duration({ minutes }: { minutes: number | null }) {
  if (minutes == null) return <span className="text-muted-foreground">—</span>;
  return <span className="tabular">{minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${minutes % 60} min`}</span>;
}

export function KevBadge({ due }: { due?: string | null }) {
  return (
    <Tooltip content={`Listed in CISA Known Exploited Vulnerabilities${due ? ` — remediation due ${due}` : ""}`}>
      <Badge className="border-sev-critical/40 bg-sev-critical/10 text-sev-critical"><ShieldAlert /> Exploited</Badge>
    </Tooltip>
  );
}

export function Categories({ items }: { items: string[] }) {
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((c) => <Badge key={c} variant="outline">{titleCase(c.replace("kubernetes_docker", "k8s/docker"))}</Badge>)}
    </div>
  );
}

export function Th({ children, className }: { children?: React.ReactNode; className?: string }) {
  return <th className={cn("whitespace-nowrap px-3 py-2 text-left text-xs font-medium text-muted-foreground", className)}>{children}</th>;
}

export function Td({ children, className }: { children?: React.ReactNode; className?: string }) {
  return <td className={cn("px-3 py-2.5 align-top text-sm", className)}>{children}</td>;
}
