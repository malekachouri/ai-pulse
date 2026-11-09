"use client";

import { Search, X } from "lucide-react";
import { useEffect, useState } from "react";

import { MultiSelect } from "@/components/feed/multi-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { activeFilterCount, type DateRange, type FeedState } from "@/lib/feed-params";
import { ITEM_TYPE_LABEL, SEVERITIES, SEVERITY_COLOR, SEVERITY_LABEL } from "@/lib/labels";
import { useCategories, useSources } from "@/lib/queries";
import type { ItemType, Severity, SortOrder } from "@/lib/types";
import { cn } from "@/lib/utils";

export function FeedFilters({
  state,
  onChange,
  typeOptions,
  showSeverity,
}: {
  state: FeedState;
  onChange: (patch: Partial<FeedState>) => void;
  typeOptions: ItemType[];
  showSeverity: boolean;
}) {
  const categories = useCategories();
  const sources = useSources();
  const [q, setQ] = useState(state.q);

  // Keep the input in sync with back/forward navigation.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- mirror external URL state into the input
    setQ(state.q);
  }, [state.q]);

  // Debounced search.
  useEffect(() => {
    if (q === state.q) return;
    const t = setTimeout(() => onChange({ q: q.trim(), page: 1 }), 350);
    return () => clearTimeout(t);
  }, [q, state.q, onChange]);

  const set = (patch: Partial<FeedState>) => onChange({ ...patch, page: 1 });
  const active = activeFilterCount(state);

  return (
    <div className="mb-5 space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            maxLength={300}
            placeholder="Search titles and content…"
            aria-label="Search this feed"
            className="pl-9"
          />
        </div>
        <NativeSelect
          aria-label="Sort by"
          className="sm:w-48"
          value={state.sort}
          onChange={(e) => set({ sort: e.target.value as SortOrder })}
        >
          <option value="latest">Sort: Latest</option>
          <option value="importance">Sort: Importance</option>
          <option value="relevance" disabled={!state.q}>
            Sort: Relevance{state.q ? "" : " (needs search)"}
          </option>
        </NativeSelect>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {typeOptions.length > 1 && (
          <MultiSelect
            label="Type"
            options={typeOptions.map((t) => ({ value: t, label: ITEM_TYPE_LABEL[t] }))}
            value={state.types}
            onChange={(v) => set({ types: v as ItemType[] })}
          />
        )}
        <MultiSelect
          label="Category"
          options={(categories.data ?? []).map((c) => ({ value: c.slug, label: c.name }))}
          value={state.categories}
          onChange={(v) => set({ categories: v })}
          emptyText={categories.isError ? "Couldn't load categories" : "Loading…"}
        />
        <MultiSelect
          label="Source"
          options={(sources.data ?? []).map((s) => ({ value: s.slug, label: s.name }))}
          value={state.sources}
          onChange={(v) => set({ sources: v })}
          emptyText={sources.isError ? "Couldn't load sources" : "No sources configured yet"}
        />
        <NativeSelect
          aria-label="Date range"
          className="w-36"
          value={state.range}
          onChange={(e) => set({ range: e.target.value as DateRange })}
        >
          <option value="any">Any time</option>
          <option value="24h">Last 24 hours</option>
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
          <option value="custom">Custom range…</option>
        </NativeSelect>
        {state.range === "custom" && (
          <div className="flex items-center gap-1.5">
            <Input
              type="date"
              aria-label="From date"
              className="w-38"
              value={state.from}
              max={state.to || undefined}
              onChange={(e) => set({ from: e.target.value })}
            />
            <span className="text-xs text-muted-foreground">to</span>
            <Input
              type="date"
              aria-label="To date"
              className="w-38"
              value={state.to}
              min={state.from || undefined}
              onChange={(e) => set({ to: e.target.value })}
            />
          </div>
        )}
        <NativeSelect
          aria-label="Minimum importance"
          className="w-44"
          value={state.minImportance ?? ""}
          onChange={(e) => set({ minImportance: e.target.value === "" ? null : Number(e.target.value) })}
        >
          <option value="">Any importance</option>
          <option value="25">Importance ≥ 25</option>
          <option value="50">Importance ≥ 50</option>
          <option value="75">Importance ≥ 75</option>
          <option value="90">Importance ≥ 90</option>
        </NativeSelect>
        {active > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              set({ types: [], categories: [], sources: [], severities: [], minImportance: null, range: "any", from: "", to: "" })
            }
          >
            <X /> Clear filters
          </Button>
        )}
      </div>

      {showSeverity && (
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Severity filter">
          <span className="mr-1 text-xs text-muted-foreground">Severity</span>
          {SEVERITIES.map((s: Severity) => {
            const on = state.severities.includes(s);
            return (
              <button
                key={s}
                type="button"
                aria-pressed={on}
                onClick={() =>
                  set({ severities: on ? state.severities.filter((x) => x !== s) : [...state.severities, s] })
                }
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
                  on ? "border-foreground/40 bg-accent font-medium text-foreground" : "text-muted-foreground hover:bg-accent/60",
                )}
              >
                <span className="size-2 rounded-full" style={{ backgroundColor: SEVERITY_COLOR[s] }} aria-hidden />
                {SEVERITY_LABEL[s]}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
