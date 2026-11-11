"use client";

import { ScrollText } from "lucide-react";
import { useState } from "react";

import { StaffGate, useIsStaff } from "@/components/admin/admin-shell";
import { Pagination } from "@/components/feed/pagination";
import { PageHeader } from "@/components/layout/page-header";
import { Td, Th } from "@/components/radar/shared";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states/states";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { useAuditLogs } from "@/lib/queries";
import { formatDateTime } from "@/lib/utils";

const TARGETS = ["", "user", "source", "ingestion", "ai", "alerts"];

function Audit() {
  const { admin } = useIsStaff();
  const [action, setAction] = useState("");
  const [target, setTarget] = useState("");
  const [page, setPage] = useState(1);
  const logs = useAuditLogs({ action: action || undefined, target_type: target || undefined, page, page_size: 50 }, admin);
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Audit log</CardTitle>
          <CardDescription>Append-only record of administrative actions: who, what, on which object, from which IP.</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 sm:grid-cols-[1fr_200px]">
          <Input
            aria-label="Filter by action"
            placeholder="Action, e.g. user.update or source.create"
            value={action}
            onChange={(e) => (setAction(e.target.value.trim()), setPage(1))}
          />
          <NativeSelect aria-label="Filter by target" value={target} onChange={(e) => (setTarget(e.target.value), setPage(1))}>
            {TARGETS.map((t) => (
              <option key={t} value={t}>
                {t || "All targets"}
              </option>
            ))}
          </NativeSelect>
        </div>
        {logs.isLoading ? (
          <ListSkeleton rows={4} />
        ) : logs.isError ? (
          <ErrorState error={logs.error} onRetry={() => logs.refetch()} />
        ) : !logs.data?.items.length ? (
          <EmptyState icon={ScrollText} title="No entries" description="Administrative actions appear here as they happen." />
        ) : (
          <>
            <div className="overflow-x-auto rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring" tabIndex={0} role="region" aria-label="Audit log table">
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr className="border-b">
                    <Th>When</Th>
                    <Th>Actor</Th>
                    <Th>Action</Th>
                    <Th>Target</Th>
                    <Th>Details</Th>
                    <Th>IP</Th>
                  </tr>
                </thead>
                <tbody>
                  {logs.data.items.map((l) => (
                    <tr key={l.id} className="border-b align-top last:border-0">
                      <Td className="whitespace-nowrap text-xs text-muted-foreground">{formatDateTime(l.created_at)}</Td>
                      <Td>{l.actor_email ?? <span className="text-muted-foreground">system</span>}</Td>
                      <Td>
                        <code className="text-xs">{l.action}</code>
                      </Td>
                      <Td className="text-xs">
                        {l.target_type}
                        {l.target_id && <span className="block font-mono text-[10px] text-muted-foreground">{l.target_id}</span>}
                      </Td>
                      <Td className="max-w-[320px]">
                        <code className="line-clamp-3 break-all text-[11px] text-muted-foreground" title={JSON.stringify(l.details)}>
                          {Object.keys(l.details).length ? JSON.stringify(l.details) : "—"}
                        </code>
                      </Td>
                      <Td className="text-xs text-muted-foreground">{l.ip_address ?? "—"}</Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={logs.data.page} pages={logs.data.pages} total={logs.data.total} pageSize={logs.data.page_size} onChange={setPage} />
          </>
        )}
      </CardContent>
    </Card>
  );
}

export default function AdminAuditPage() {
  return (
    <>
      <PageHeader title="Audit log" description="Who changed what, and when." icon={ScrollText} />
      <StaffGate adminOnly what="the audit log">
        <Audit />
      </StaffGate>
    </>
  );
}
