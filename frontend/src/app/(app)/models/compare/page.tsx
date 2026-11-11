"use client";

import { Check, ExternalLink, Plus, Scale, X } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useModelComparison, useModelPicker } from "@/lib/queries";
import type { BenchmarkCell, ComparedModel, SourcedFact } from "@/lib/types";
import { safeUrl } from "@/lib/utils";

const MAX = 4;

const day = (d: string | null) => (d ? d.slice(0, 10) : null);

function Source({ href, label }: { href: string; label: string }) {
  return (
    <a href={safeUrl(href)} target="_blank" rel="noopener noreferrer" className="ml-1 inline-flex items-center text-primary" aria-label={label}>
      <ExternalLink className="size-3" aria-hidden />
    </a>
  );
}

function Fact({ f, what, model }: { f: SourcedFact | null; what: string; model: string }) {
  if (!f) return <span className="text-xs italic text-muted-foreground">not reported</span>;
  return (
    <span>
      {f.value}
      <Source href={f.source_url} label={`Source of ${what} for ${model}`} />
      {f.date && <span className="block text-[11px] text-muted-foreground">{day(f.date)}</span>}
    </span>
  );
}

function Score({ c, bench, model }: { c: BenchmarkCell | null; bench: string; model: string }) {
  if (!c) return <span className="text-xs italic text-muted-foreground">not reported</span>;
  return (
    <span>
      <span className="tabular font-semibold">{c.value}</span>
      <Source href={c.source_url} label={`Source of ${bench} for ${model}: ${c.source_title}`} />
      <span className="block text-[11px] text-muted-foreground">
        {c.source}
        {c.version && ` · v${c.version}`}
        {c.date && ` · ${day(c.date)}`}
      </span>
      <span className="block max-w-[240px] text-[11px] italic text-muted-foreground">“{c.quote}”</span>
    </span>
  );
}

function Picker({ ids, onChange }: { ids: string[]; onChange: (ids: string[]) => void }) {
  const [q, setQ] = useState("");
  const models = useModelPicker(q);
  const toggle = (id: string) =>
    onChange(ids.includes(id) ? ids.filter((x) => x !== id) : ids.length < MAX ? [...ids, id] : ids);
  return (
    <Card>
      <CardContent className="space-y-3 pt-5">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold">Choose 2 to {MAX} models</h2>
            <p className="text-xs text-muted-foreground">{ids.length} selected</p>
          </div>
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search models" aria-label="Search models" className="h-8 w-full sm:w-64" />
        </div>
        {models.isError ? (
          <ErrorState error={models.error} onRetry={() => models.refetch()} />
        ) : !models.data ? (
          <ListSkeleton rows={1} />
        ) : !models.data.items.length ? (
          <p className="text-sm text-muted-foreground">No tracked model matches.</p>
        ) : (
          <ul className="flex flex-wrap gap-2" aria-label="Tracked models">
            {models.data.items.map((m) => {
              const on = ids.includes(m.id);
              return (
                <li key={m.id}>
                  <Button
                    variant={on ? "default" : "outline"}
                    size="sm"
                    aria-pressed={on}
                    disabled={!on && ids.length >= MAX}
                    onClick={() => toggle(m.id)}
                  >
                    {on ? <Check /> : <Plus />} {m.name} <span className="font-normal opacity-80">· {m.provider}</span>
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function Results({ ids, onRemove }: { ids: string[]; onRemove: (id: string) => void }) {
  const q = useModelComparison(ids);
  if (ids.length < 2) {
    return <EmptyState icon={Scale} title="Pick at least two models" description="Scores appear only when a collected source states them, with its link and date." />;
  }
  if (q.isLoading) return <ListSkeleton rows={2} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data;
  if (!d) return null;
  const facts: { label: string; get: (m: ComparedModel) => React.ReactNode }[] = [
    { label: "Provider", get: (m) => m.provider },
    { label: "Weights", get: (m) => (m.is_open_weights == null ? <span className="text-xs italic text-muted-foreground">unknown</span> : m.is_open_weights ? "Open" : "Closed") },
    { label: "Latest release", get: (m) => <Fact f={m.latest_release} what="the latest release" model={m.name} /> },
    { label: "Context window", get: (m) => <Fact f={m.context_window} what="the context window" model={m.name} /> },
    { label: "License", get: (m) => <Fact f={m.license} what="the license" model={m.name} /> },
  ];
  return (
    <section aria-labelledby="comparison-title" className="space-y-2">
      <h2 id="comparison-title" className="text-lg font-semibold">Comparison</h2>
      <p className="text-xs text-muted-foreground">{d.method}</p>
      <div className="overflow-x-auto rounded-xl border bg-card outline-none focus-visible:ring-2 focus-visible:ring-ring" tabIndex={0} role="region" aria-label="Model comparison table">
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr className="border-b text-left">
              <th scope="col" className="w-40 p-3 text-xs font-medium text-muted-foreground">
                <span className="sr-only">Attribute</span>
              </th>
              {d.models.map((m) => (
                <th key={m.id} scope="col" className="p-3 align-top">
                  <span className="flex items-start justify-between gap-2">
                    <span className="font-semibold">{m.name}</span>
                    <Button variant="ghost" size="icon" className="size-6" onClick={() => onRemove(m.id)} aria-label={`Remove ${m.name}`}>
                      <X className="size-3.5" />
                    </Button>
                  </span>
                  <span className="block text-[11px] font-normal text-muted-foreground">
                    {m.benchmarks_reported} benchmark{m.benchmarks_reported === 1 ? "" : "s"} from {m.releases_considered} release{m.releases_considered === 1 ? "" : "s"}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y">
            {facts.map((f) => (
              <tr key={f.label}>
                <th scope="row" className="p-3 text-left text-xs font-medium text-muted-foreground">{f.label}</th>
                {d.models.map((m) => (
                  <td key={m.id} className="p-3 align-top">{f.get(m)}</td>
                ))}
              </tr>
            ))}
            <tr className="bg-muted/40">
              <th scope="colgroup" colSpan={d.models.length + 1} className="px-3 py-2 text-left text-xs font-semibold">
                Benchmarks quoted by the sources
              </th>
            </tr>
            {d.benchmarks.length === 0 ? (
              <tr>
                <td colSpan={d.models.length + 1} className="p-3 text-xs italic text-muted-foreground">
                  None of the collected sources for these models quote benchmark scores.
                </td>
              </tr>
            ) : (
              d.benchmarks.map((b) => (
                <tr key={b.name}>
                  <th scope="row" className="p-3 text-left align-top text-xs font-medium">
                    {b.name}
                    {b.reported_by < d.models.length && <Badge variant="outline" className="ml-1.5 align-middle text-[10px]">partial</Badge>}
                  </th>
                  {d.models.map((m) => (
                    <td key={m.id} className="p-3 align-top">
                      <Score c={b.cells[m.id] ?? null} bench={b.name} model={m.name} />
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {d.note && <p className="text-xs text-muted-foreground">{d.note}</p>}
    </section>
  );
}

function Compare() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const ids = [...new Set(params.getAll("ids"))].slice(0, MAX);
  const setIds = (next: string[]) => {
    const sp = new URLSearchParams();
    next.forEach((i) => sp.append("ids", i));
    router.replace(next.length ? `${pathname}?${sp}` : pathname, { scroll: false });
  };
  return (
    <div className="space-y-6">
      <Picker ids={ids} onChange={setIds} />
      <Results ids={ids} onRemove={(id) => setIds(ids.filter((x) => x !== id))} />
    </div>
  );
}

export default function CompareModelsPage() {
  return (
    <>
      <PageHeader
        title="Compare AI models"
        description="Side by side, with only the numbers and facts that collected sources state: every value links to its source and date. Nothing is estimated."
        icon={Scale}
      />
      <Suspense fallback={<ListSkeleton />}>
        <Compare />
      </Suspense>
    </>
  );
}
