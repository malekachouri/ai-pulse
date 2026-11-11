"use client";

import { Bell, CheckCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { SeverityBadge } from "@/components/feed/badges";
import { KIND_META, NotificationLink } from "@/components/notifications/notification-row";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";
import { useMarkNotificationRead, useNotifications, useUnreadCount } from "@/lib/queries";
import { cn, timeAgo } from "@/lib/utils";

export function NotificationCenter() {
  const { status } = useAuth();
  const [open, setOpen] = useState(false);
  const unread = useUnreadCount().data?.unread ?? 0;
  // The badge text starts the button's name ("15 unread notifications"): WCAG 2.5.3, label in name.
  const shown = unread > 99 ? "99+" : String(unread);
  const list = useNotifications(open);
  const mark = useMarkNotificationRead();

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative"
          aria-label={unread ? `${shown} unread notifications` : "Notifications"}
        >
          <Bell />
          {unread > 0 && (
            <span aria-hidden className="absolute right-1.5 top-1.5 flex min-w-4 items-center justify-center rounded-full bg-destructive-solid px-1 text-[10px] font-semibold leading-4 text-white">
              {shown}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[min(92vw,380px)] p-0">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <p className="text-sm font-semibold">Notifications</p>
          {status === "authenticated" && unread > 0 && (
            <Button variant="ghost" size="sm" onClick={() => mark.mutate("all")} disabled={mark.isPending}>
              <CheckCheck /> Mark all read
            </Button>
          )}
        </div>
        <div className="max-h-[420px] overflow-y-auto">
          {status !== "authenticated" ? (
            <p className="px-4 py-8 text-center text-sm text-muted-foreground">
              <Link href="/login" className="font-medium text-primary hover:underline">
                Sign in
              </Link>{" "}
              to receive alerts for critical CVEs, outages and releases.
            </p>
          ) : list.isLoading ? (
            <div className="space-y-3 p-4">
              <Skeleton className="h-10" />
              <Skeleton className="h-10" />
            </div>
          ) : list.isError ? (
            <p className="px-4 py-8 text-center text-sm text-muted-foreground">Couldn&apos;t load notifications.</p>
          ) : !list.data?.items.length ? (
            <p className="px-4 py-8 text-center text-sm text-muted-foreground">
              You&apos;re all caught up. Alerts appear here once matching items are collected.
            </p>
          ) : (
            <ul className="divide-y">
              {list.data.items.map((n) => {
                return (
                  <li key={n.id} className={cn("flex gap-3 px-4 py-3", !n.read_at && "bg-primary/5")}>
                    <span
                      className={cn("mt-1.5 size-2 shrink-0 rounded-full", n.read_at ? "bg-transparent" : "bg-primary")}
                      aria-label={n.read_at ? "Read" : "Unread"}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                          {(KIND_META[n.kind] ?? KIND_META.system).label}
                        </span>
                        {n.severity !== "info" && <SeverityBadge severity={n.severity} />}
                        <span className="text-[11px] text-muted-foreground">{timeAgo(n.created_at)}</span>
                      </div>
                      <p className="mt-1 text-sm leading-snug">{n.title}</p>
                      <div className="mt-1.5 flex gap-3 text-xs">
                        <NotificationLink link={n.link} />
                        {!n.read_at && (
                          <button className="text-muted-foreground hover:text-foreground" onClick={() => mark.mutate(n.id)}>
                            Mark read
                          </button>
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        {status === "authenticated" && (
          <div className="border-t px-4 py-2 text-center">
            <Link href="/notifications" onClick={() => setOpen(false)} className="text-xs font-medium text-primary hover:underline">
              View all notifications
            </Link>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
