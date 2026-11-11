"use client";

import { History, Loader2, RotateCcw } from "lucide-react";
import { useState } from "react";

import { StaffGate, useIsStaff } from "@/components/admin/admin-shell";
import { Pagination } from "@/components/feed/pagination";
import { PageHeader } from "@/components/layout/page-header";
import { Td, Th } from "@/components/radar/shared";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/native-select";
import { useIngestionActions, useJobs, useRetryFailedJobs } from "@/lib/queries";
import type { JobStatus } from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";

const STATUS_TONE: Record<JobStatus, string> = {
  succeeded: "text-emerald-700 dark:text-emerald-400",
  partial: "text-amber-700 dark:text-amber-300",
  failed: "text-sev-critical",
  running: "text-primary",
  pending: "text-muted-foreground",
};

function Jobs() {
  const { staff } = useIsStaff();
  const [status, setStatus] = useState<JobStatus | "">("");
  const [page, setPage] = useState(1);
  const [hours, setHours] = useState(24);
  const jobs = useJobs({ status: status ? [status] : undefined, page, page_size: 25, sort: "-started_at" }, staff);
  const { retry } = useIngestionActions();
  const bulk = useRetryFailedJobs();

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Failed task management</CardTitle>
            <CardDescription>
              Failed runs are retried automatically with exponential backoff. Here you can retry one job, or every enabled source
              whose most recent run failed. Retries are idempotent and audited.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2">
          <NativeSelect aria-label="Window" value={hours} onChange={(e) => setHours(Number(e.target.value))} className="w-44">
            {[6, 24, 72, 168].map((h) => (
              <option key={h} value={h}>
                Failed in the last {h < 48 ? `${h} h` : `${h / 24} days`}
              </option>
            ))}
          </NativeSelect>
          <Button variant="outline" onClick={() => bulk.mutate(hours)} disabled={bulk.isPending}>
            {bulk.isPending ? <Loader2 className="animate-spin" /> : <RotateCcw />} Retry all failed sources
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Ingestion job history</CardTitle>
            <CardDescription>Every run with its trigger, duration, item counts and errors. Refreshes every 30 seconds.</CardDescription>
          </div>
          <NativeSelect aria-label="Filter by status" value={status} onChange={(e) => (setStatus(e.target.value as JobStatus | ""), setPage(1))} className="w-40">
            <option value="">All statuses</option>
            {(["failed", "partial", "succeeded", "running", "pending"] as JobStatus[]).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </NativeSelect>
        </CardHeader>
        <CardContent>
          {jobs.isLoading ? (
            <ListSkeleton rows={4} />
          ) : jobs.isError ? (
            <ErrorState error={jobs.error} onRetry={() => jobs.refetch()} />
          ) : !jobs.data?.items.length ? (
            <EmptyState icon={History} title="No jobs" description="Runs appear here once the scheduler or an admin starts one." />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[860px] text-sm">
                  <thead>
                    <tr className="border-b">
                      <Th>Source</Th>
                      <Th>Status</Th>
                      <Th>Trigger</Th>
                      <Th>Started</Th>
                      <Th className="text-right">Duration</Th>
                      <Th className="text-right">Fetched / new / updated</Th>
                      <Th>Error</Th>
                      <Th>
                    <span className="sr-only">Actions</span>
                  </Th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.data.items.map((j) => (
                      <tr key={j.id} className="border-b align-top last:border-0">
                        <Td className="font-medium">{j.source?.name ?? j.source_id.slice(0, 8)}</Td>
                        <Td>
                          <span className={cn("font-semibold", STATUS_TONE[j.status])}>{j.status}</span>
                          {j.attempt > 1 && <span className="ml-1 text-xs text-muted-foreground">attempt {j.attempt}</span>}
                        </Td>
                        <Td>
                          <Badge variant="outline">{j.trigger}</Badge>
                        </Td>
                        <Td className="whitespace-nowrap text-xs text-muted-foreground">{formatDateTime(j.started_at)}</Td>
                        <Td className="tabular text-right">{j.duration_seconds != null ? `${j.duration_seconds.toFixed(1)} s` : "—"}</Td>
                        <Td className="tabular text-right">
                          {j.items_fetched} / {j.items_created} / {j.items_updated}
                        </Td>
                        <Td className="max-w-[280px]">
                          {j.error ? (
                            <p className="line-clamp-2 text-xs text-muted-foreground" title={j.error}>
                              {j.error}
                            </p>
                          ) : j.errors.length ? (
                            <p className="text-xs text-muted-foreground">{j.errors.length} item error(s)</p>
                          ) : null}
                        </Td>
                        <Td>
                          {(j.status === "failed" || j.status === "partial") && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => retry.mutate(j.id)}
                              disabled={retry.isPending && retry.variables === j.id}
                              aria-label={`Retry ${j.source?.name ?? "job"}`}
                            >
                              <RotateCcw /> Retry
                            </Button>
                          )}
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={jobs.data.page} pages={jobs.data.pages} total={jobs.data.total} pageSize={jobs.data.page_size} onChange={setPage} />
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function AdminJobsPage() {
  return (
    <>
      <PageHeader title="Jobs & failures" description="Ingestion history and failed task management." icon={History} />
      <StaffGate what="job history">
        <Jobs />
      </StaffGate>
    </>
  );
}
