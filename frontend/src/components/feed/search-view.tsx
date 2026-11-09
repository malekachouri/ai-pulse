"use client";

import { Search, SearchX } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ArticleCard } from "@/components/feed/article-card";
import { Pagination } from "@/components/feed/pagination";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states/states";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { parseHighlights } from "@/lib/highlight";
import { ITEM_TYPE_LABEL } from "@/lib/labels";
import { useSearch, useSearchCapabilities } from "@/lib/queries";
import type { ItemType } from "@/lib/types";
import { cn } from "@/lib/utils";

const TYPES = Object.keys(ITEM_TYPE_LABEL) as ItemType[];

function Snippet({ text }: { text: string }) {
  return (
    <p className="mb-2 rounded-lg bg-muted/50 px-3 py-2 text-sm leading-relaxed text-muted-foreground">
      <span className="sr-only">Matching excerpt: </span>…
      {parseHighlights(text).map((s, i) =>
        s.match ? (
          <mark key={i} className="rounded bg-primary/20 px-0.5 text-foreground">
            {s.text}
          </mark>
        ) : (
          <span key={i}>{s.text}</span>
        ),
      )}
      …
    </p>
  );
}

export function SearchView() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const q = (params.get("q") ?? "").slice(0, 300);
  const types = params.getAll("type").filter((t): t is ItemType => TYPES.includes(t as ItemType));
  const page = Math.max(1, Number.parseInt(params.get("page") ?? "1", 10) || 1);
  const caps = useSearchCapabilities();
  const rawMode = params.get("mode");
  const mode = rawMode === "semantic" || rawMode === "hybrid" ? rawMode : "keyword";
  const [draft, setDraft] = useState(q);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- mirror URL state into the input
    setDraft(q);
  }, [q]);

  const go = (next: { q?: string; types?: ItemType[]; page?: number; mode?: string }) => {
    const sp = new URLSearchParams();
    const nq = next.q ?? q;
    if (nq) sp.set("q", nq);
    const nm = next.mode ?? mode;
    if (nm !== "keyword") sp.set("mode", nm);
    (next.types ?? types).forEach((t) => sp.append("type", t));
    if ((next.page ?? 1) > 1) sp.set("page", String(next.page));
    router.replace(`${pathname}?${sp.toString()}`, { scroll: false });
  };

  const res = useSearch({ q, item_type: types.length ? types : undefined, page, mode });

  return (
    <section aria-label="Search results">
      <form
        className="relative mb-3 flex gap-2"
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          go({ q: draft.trim(), page: 1 });
        }}
      >
        <div className="relative flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={300}
          placeholder='Try "kubernetes vulnerability" or "rag -benchmark"'
          aria-label="Search query"
          className="h-10 pl-9"
        />
        </div>
        <NativeSelect aria-label="Search mode" className="w-40" value={mode} onChange={(e) => go({ mode: e.target.value, page: 1 })}>
          <option value="keyword">Keyword</option>
          <option value="semantic" disabled={!caps.data?.semantic}>Semantic{caps.data?.semantic ? "" : " (unavailable)"}</option>
          <option value="hybrid" disabled={!caps.data?.hybrid}>Hybrid{caps.data?.hybrid ? "" : " (unavailable)"}</option>
        </NativeSelect>
      </form>
      <div className="mb-5 flex flex-wrap gap-1.5" role="group" aria-label="Filter by type">
        {TYPES.map((t) => {
          const on = types.includes(t);
          return (
            <button
              key={t}
              type="button"
              aria-pressed={on}
              onClick={() => go({ types: on ? types.filter((x) => x !== t) : [...types, t], page: 1 })}
              className={cn(
                "rounded-full border px-2.5 py-1 text-xs transition-colors",
                on ? "border-primary/50 bg-primary/10 font-medium text-foreground" : "text-muted-foreground hover:bg-accent/60",
              )}
            >
              {ITEM_TYPE_LABEL[t]}
            </button>
          );
        })}
      </div>

      {q.length < 2 ? (
        <EmptyState icon={Search} title="Search everything AI Pulse has collected" description="Supports quoted phrases, OR, and -exclusions. Enter at least 2 characters." />
      ) : res.isLoading ? (
        <ListSkeleton />
      ) : res.isError ? (
        <ErrorState error={res.error} onRetry={() => res.refetch()} />
      ) : !res.data?.items.length ? (
        <EmptyState icon={SearchX} title={`No results for “${q}”`} description="Try fewer or different words, or remove type filters." />
      ) : (
        <>
          <p className="mb-3 text-xs text-muted-foreground" aria-live="polite">
            <span className="tabular">{res.data.total.toLocaleString("en")}</span> result{res.data.total === 1 ? "" : "s"}, ranked by
            relevance{res.isFetching && " · updating…"}
          </p>
          <div className="grid gap-4">
            {res.data.items.map((h) => (
              <div key={h.article.id}>
                {h.snippet && <Snippet text={h.snippet} />}
                <ArticleCard article={h.article} />
              </div>
            ))}
          </div>
          <Pagination page={res.data.page} pages={res.data.pages} total={res.data.total} pageSize={res.data.page_size} onChange={(p) => go({ page: p })} />
        </>
      )}
    </section>
  );
}
