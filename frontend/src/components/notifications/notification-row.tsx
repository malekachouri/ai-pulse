"use client";

import { AlertOctagon, Bug, Cpu, ExternalLink, Mail, MailOpen, Server, ShieldAlert, Sunrise, Trash2, type LucideIcon } from "lucide-react";
import Link from "next/link";

import { SeverityBadge } from "@/components/feed/badges";
import { Button } from "@/components/ui/button";
import type { Notification, NotificationKind } from "@/lib/types";
import { cn, formatDateTime, safeUrl, timeAgo } from "@/lib/utils";

export const NOTIFICATION_GROUPS: { key: string; label: string; kinds: NotificationKind[] }[] = [
  { key: "all", label: "All", kinds: [] },
  { key: "critical", label: "Critical alerts", kinds: ["critical_alert"] },
  { key: "models", label: "Model releases", kinds: ["model_release"] },
  { key: "security", label: "Bugs & vulnerabilities", kinds: ["vulnerability", "bug"] },
  { key: "incidents", label: "Incidents", kinds: ["incident"] },
  { key: "briefings", label: "Briefings", kinds: ["briefing"] },
];

export const KIND_META: Record<NotificationKind, { label: string; icon: LucideIcon; tone: string }> = {
  critical_alert: { label: "Critical alert", icon: AlertOctagon, tone: "text-red-600 dark:text-red-400" },
  model_release: { label: "Model release", icon: Cpu, tone: "text-primary" },
  vulnerability: { label: "Vulnerability", icon: ShieldAlert, tone: "text-orange-600 dark:text-orange-400" },
  bug: { label: "Bug", icon: Bug, tone: "text-amber-700 dark:text-amber-400" },
  incident: { label: "Incident", icon: Server, tone: "text-orange-600 dark:text-orange-400" },
  briefing: { label: "Briefing", icon: Sunrise, tone: "text-violet-600 dark:text-violet-300" },
  system: { label: "System", icon: Mail, tone: "text-muted-foreground" },
};

/** Internal links (`/briefing?...`) stay in the app; anything else must be a safe external URL. */
export function NotificationLink({ link, className }: { link: string | null; className?: string }) {
  if (!link) return null;
  if (link.startsWith("/") && !link.startsWith("//")) {
    return (
      <Link href={link} className={cn("inline-flex items-center gap-1 text-primary hover:underline", className)}>
        Open
      </Link>
    );
  }
  const href = safeUrl(link);
  if (!href) return null;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={cn("inline-flex items-center gap-1 text-primary hover:underline", className)}>
      Source <ExternalLink className="size-3" />
    </a>
  );
}

export function NotificationRow({
  n,
  onAction,
  busy,
}: {
  n: Notification;
  onAction: (a: { type: "read" | "unread" | "delete" }) => void;
  busy?: boolean;
}) {
  const meta = KIND_META[n.kind] ?? KIND_META.system;
  const Icon = meta.icon;
  const unread = !n.read_at;
  return (
    <li className={cn("flex gap-3 px-4 py-3", unread && "bg-primary/5")}>
      <Icon className={cn("mt-0.5 size-4 shrink-0", meta.tone)} aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
          <span className="font-semibold uppercase tracking-wide">{meta.label}</span>
          {n.severity !== "info" && <SeverityBadge severity={n.severity} />}
          <time dateTime={n.created_at} title={formatDateTime(n.created_at)}>
            {timeAgo(n.created_at)}
          </time>
          {unread && <span className="size-2 rounded-full bg-primary" role="img" aria-label="Unread" />}
        </div>
        <p className={cn("mt-1 text-sm leading-snug", unread && "font-medium")}>{n.title}</p>
        {n.body && <p className="mt-0.5 line-clamp-3 text-xs text-muted-foreground">{n.body}</p>}
        <div className="mt-1.5 flex items-center gap-3 text-xs">
          <NotificationLink link={n.link} />
        </div>
      </div>
      <div className="flex shrink-0 items-start gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          disabled={busy}
          onClick={() => onAction({ type: unread ? "read" : "unread" })}
          aria-label={unread ? "Mark as read" : "Mark as unread"}
          title={unread ? "Mark as read" : "Mark as unread"}
        >
          {unread ? <MailOpen /> : <Mail />}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="size-8 text-muted-foreground hover:text-destructive"
          disabled={busy}
          onClick={() => onAction({ type: "delete" })}
          aria-label="Delete notification"
          title="Delete"
        >
          <Trash2 />
        </Button>
      </div>
    </li>
  );
}
