"use client";

import { Bell, BellOff, CheckCheck, Settings2 } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { Pagination } from "@/components/feed/pagination";
import { PageHeader } from "@/components/layout/page-header";
import { NOTIFICATION_GROUPS, NotificationRow } from "@/components/notifications/notification-row";
import { EmptyState, ErrorState, ListSkeleton, SignInRequired } from "@/components/states/states";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/lib/auth";
import { useNotificationAction, useNotificationList, useUnreadCount } from "@/lib/queries";
import type { NotificationKind } from "@/lib/types";

const ALL_GROUP = { key: "all", label: "All", kinds: [] as NotificationKind[] };

function Center() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const group = NOTIFICATION_GROUPS.find((g) => g.key === params.get("tab")) ?? ALL_GROUP;
  const unreadOnly = params.get("unread") === "1";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const counts = useUnreadCount().data;
  const list = useNotificationList({ kind: group.kinds, unread_only: unreadOnly, page });
  const act = useNotificationAction();

  const update = (next: Record<string, string | null>) => {
    const sp = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(next)) {
      if (v === null) sp.delete(k);
      else sp.set(k, v);
    }
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };
  const unreadIn = (kinds: NotificationKind[]) =>
    kinds.length ? kinds.reduce((n, k) => n + (counts?.by_kind[k] ?? 0), 0) : (counts?.unread ?? 0);
  const groupUnread = unreadIn(group.kinds);

  return (
    <>
      <Tabs value={group.key} onValueChange={(v) => update({ tab: v === "all" ? null : v, page: null })}>
        <TabsList className="mb-4 flex h-auto flex-wrap justify-start">
          {NOTIFICATION_GROUPS.map((g) => {
            const n = unreadIn(g.kinds);
            return (
              <TabsTrigger key={g.key} value={g.key} className="gap-1.5">
                {g.label}
                {n > 0 && (
                  <span className="tabular rounded-full bg-primary/15 px-1.5 text-[10px] font-semibold text-primary" aria-label={`${n} unread`}>
                    {n}
                  </span>
                )}
              </TabsTrigger>
            );
          })}
        </TabsList>
        {/* The list is the active tab's panel, so each tab's aria-controls points at a real element. */}
        <TabsContent value={group.key}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <Checkbox checked={unreadOnly} onCheckedChange={(c) => update({ unread: c ? "1" : null, page: null })} />
          Unread only
        </label>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/settings#notifications">
              <Settings2 /> Preferences
            </Link>
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={groupUnread === 0 || act.isPending}
            onClick={() => act.mutate({ type: "read-all", kind: group.kinds.length ? group.kinds : undefined })}
          >
            <CheckCheck /> Mark {group.key === "all" ? "all" : "these"} read
          </Button>
        </div>
      </div>
      {list.isLoading ? (
        <ListSkeleton />
      ) : list.isError ? (
        <ErrorState error={list.error} onRetry={() => list.refetch()} />
      ) : !list.data?.items.length ? (
        <EmptyState
          icon={BellOff}
          title={unreadOnly ? "No unread notifications" : "No notifications here yet"}
          description="Alerts appear when collected items match your notification preferences. Each event is notified once."
        />
      ) : (
        <>
          <ul className="divide-y rounded-xl border">
            {list.data.items.map((n) => (
              <NotificationRow key={n.id} n={n} onAction={(a) => act.mutate({ ...a, id: n.id })} busy={act.isPending} />
            ))}
          </ul>
          <Pagination
            page={list.data.page}
            pages={list.data.pages}
            total={list.data.total}
            pageSize={list.data.page_size}
            onChange={(p) => update({ page: p === 1 ? null : String(p) })}
          />
        </>
      )}
        </TabsContent>
      </Tabs>
    </>
  );
}

export default function NotificationsPage() {
  const { status } = useAuth();
  return (
    <>
      <PageHeader
        title="Notifications"
        description="Critical alerts, model releases, bugs, vulnerabilities, incidents and briefing deliveries. Every alert links to its source."
        icon={Bell}
      />
      {status === "loading" ? (
        <ListSkeleton />
      ) : status !== "authenticated" ? (
        <SignInRequired what="notifications" />
      ) : (
        <Suspense fallback={<ListSkeleton />}>
          <Center />
        </Suspense>
      )}
    </>
  );
}
