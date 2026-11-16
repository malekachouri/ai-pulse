"use client";

import { Puzzle, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { Pagination } from "@/components/feed/pagination";
import { KIND, SkillCard, STACK_LABEL } from "@/components/skills/skill-card";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states/states";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { useSkillFacets, useSkills } from "@/lib/queries";
import type { SkillKind } from "@/lib/types";
import { timeAgo } from "@/lib/utils";

const PERIODS = [
  { value: "7", label: "New in 7 days" },
  { value: "1", label: "New today" },
  { value: "30", label: "New in 30 days" },
  { value: "", label: "Everything" },
];

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export default function SkillsRadarPage() {
  const [page, setPage] = useState(1);
  const [text, setText] = useState("");
  const [kind, setKind] = useState("");
  const [source, setSource] = useState("");
  const [stack, setStack] = useState("");
  const [days, setDays] = useState("7");
  const q = useDebounced(text.trim());

  const facets = useSkillFacets();
  const list = useSkills({
    page, page_size: 20, q: q || undefined, kind: kind || undefined, source: source || undefined,
    days: days || undefined, ...(stack === "any" ? { fits: true } : stack ? { stack } : {}),
  });
  const f = facets.data;
  const reset = (fn: (v: string) => void) => (e: React.ChangeEvent<HTMLSelectElement>) => { fn(e.target.value); setPage(1); };

  return (
    <>
      <PageHeader
        title="Skills Radar"
        description="New MCP servers, Claude Code plugins and Agent Skills from official listings, with how to install them and which AI Pulse technologies they cover. Facts from the listings only: AI Pulse does not review third-party code."
        icon={Puzzle}
      />
      {f && (
        <p className="mb-4 text-xs text-muted-foreground">
          {f.new_last_7_days} new this week ·{" "}
          {f.kinds.map((k) => `${k.count} ${(k.count === 1 ? KIND[k.value]?.label : KIND[k.value]?.plural) ?? k.value}`).join(" · ")}
          {f.sources.length > 0 && (
            <>
              {" · "}
              {f.sources.map((s) => `${s.name}: ${s.last_success_at ? `read ${timeAgo(s.last_success_at)}` : "not collected yet"}${s.last_error ? " (failing)" : ""}`).join(" · ")}
            </>
          )}
        </p>
      )}
      <div className="mb-4 flex flex-wrap gap-2" role="search" aria-label="Filter the skills radar">
        <div className="relative w-full sm:w-64">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input type="search" aria-label="Search name, description or publisher" placeholder="Search…" className="pl-8" value={text} onChange={(e) => { setText(e.target.value); setPage(1); }} />
        </div>
        <NativeSelect aria-label="Period" className="w-44" value={days} onChange={reset(setDays)}>
          {PERIODS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
        </NativeSelect>
        <NativeSelect aria-label="Type" className="w-40" value={kind} onChange={reset(setKind)}>
          <option value="">All types</option>
          {(Object.keys(KIND) as SkillKind[]).map((k) => <option key={k} value={k}>{KIND[k].plural}</option>)}
        </NativeSelect>
        <NativeSelect aria-label="Fits AI Pulse" className="w-56" value={stack} onChange={reset(setStack)}>
          <option value="">Any technology</option>
          <option value="any">Fits AI Pulse (any of its technologies)</option>
          {Object.entries(STACK_LABEL).map(([v, label]) => <option key={v} value={v}>{label}</option>)}
        </NativeSelect>
        <NativeSelect aria-label="Source" className="w-56" value={source} onChange={reset(setSource)}>
          <option value="">All sources</option>
          {f?.sources.map((s) => <option key={s.slug} value={s.slug}>{s.name}</option>)}
        </NativeSelect>
      </div>
      {list.isLoading ? (
        <ListSkeleton rows={4} />
      ) : list.isError ? (
        <ErrorState error={list.error} onRetry={() => list.refetch()} />
      ) : !list.data?.items.length ? (
        <EmptyState
          icon={Puzzle}
          title={f && f.kinds.length === 0 ? "Nothing collected yet" : "Nothing matches these filters"}
          description={
            f && f.kinds.length === 0
              ? "The radar sources are collected on a schedule (the MCP Registry every hour, the marketplaces every 6 hours). An administrator can run them now from Connector health."
              : days ? "Try a longer period or “Everything”: marketplace entries that existed before AI Pulse watched them are not counted as new." : "Try other filters."
          }
        />
      ) : (
        <>
          <p className="mb-2 text-xs text-muted-foreground" aria-live="polite">{list.data.total} result{list.data.total === 1 ? "" : "s"}</p>
          <div className="space-y-3">
            {list.data.items.map((s) => <SkillCard key={s.id} s={s} />)}
          </div>
          <Pagination page={page} pages={list.data.pages} total={list.data.total} pageSize={list.data.page_size} onChange={setPage} />
        </>
      )}
    </>
  );
}
