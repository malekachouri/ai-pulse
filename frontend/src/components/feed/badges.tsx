"use client";

import { BadgeCheck, CircleHelp, ShieldQuestion, TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Tooltip } from "@/components/ui/tooltip";
import { ITEM_TYPE_LABEL, SEVERITY_COLOR, SEVERITY_LABEL, VERIFICATION_LABEL } from "@/lib/labels";
import type { ItemType, Severity, VerificationStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Severity always carries a text label next to its reserved status colour (never colour alone). */
export function SeverityBadge({ severity, basis }: { severity: Severity; basis?: string | null }) {
  const badge = (
    <span
      className="inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-semibold"
      style={{
        borderColor: `color-mix(in oklab, ${SEVERITY_COLOR[severity]} 45%, transparent)`,
        backgroundColor: `color-mix(in oklab, ${SEVERITY_COLOR[severity]} 14%, transparent)`,
      }}
    >
      <span className="size-2 rounded-full" style={{ backgroundColor: SEVERITY_COLOR[severity] }} aria-hidden />
      {SEVERITY_LABEL[severity]}
    </span>
  );
  return basis ? <Tooltip content={<>Severity basis: {basis}</>}>{badge}</Tooltip> : badge;
}

export function ItemTypeBadge({ type }: { type: ItemType }) {
  return <Badge variant="secondary">{ITEM_TYPE_LABEL[type]}</Badge>;
}

const VERIFICATION_ICON: Record<VerificationStatus, typeof BadgeCheck> = {
  official: BadgeCheck,
  verified: BadgeCheck,
  unverified: ShieldQuestion,
  disputed: TriangleAlert,
};

export function VerificationBadge({ status }: { status: VerificationStatus }) {
  const Icon = VERIFICATION_ICON[status];
  const { label, hint } = VERIFICATION_LABEL[status];
  return (
    <Tooltip content={hint}>
      <span
        className={cn(
          "inline-flex items-center gap-1 text-[11px]",
          status === "official" || status === "verified"
            ? "text-emerald-700 dark:text-emerald-400"
            : "text-amber-700 dark:text-amber-400",
        )}
      >
        <Icon className="size-3.5" />
        {label}
      </span>
    </Tooltip>
  );
}

/** AI Pulse importance (0–100). Explicitly not a CVSS score. */
export function ImportanceMeter({ score, compact = false }: { score: number | null; compact?: boolean }) {
  if (score == null)
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
        <CircleHelp className="size-3.5" /> Not scored
      </span>
    );
  const value = Math.round(score);
  return (
    <Tooltip content="AI Pulse importance score (0–100): source reliability, severity, recency and impact. Not an official CVSS score.">
      <span className="inline-flex items-center gap-2 text-[11px] text-muted-foreground" aria-label={`Importance ${value} of 100`}>
        {!compact && <span>Importance</span>}
        <span className="relative h-1.5 w-14 overflow-hidden rounded-full bg-muted">
          <span
            className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-brand-blue to-brand-violet"
            style={{ width: `${Math.max(4, Math.min(100, value))}%` }}
          />
        </span>
        <span className="tabular font-semibold text-foreground">{value}</span>
      </span>
    </Tooltip>
  );
}
