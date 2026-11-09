"use client";

import { SearchX } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ArticleCard } from "@/components/feed/article-card";
import { FeedFilters } from "@/components/feed/feed-filters";
import { Pagination } from "@/components/feed/pagination";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states/states";
import { activeFilterCount, PAGE_SIZE, parseFeedState, serializeFeedState, toApiFilters, type FeedState } from "@/lib/feed-params";
import { useNews } from "@/lib/queries";
import type { ItemType } from "@/lib/types";

export interface FeedViewProps {
  /** Item types this page shows. Empty = every type (global search). */
  types: ItemType[];
  showSeverity?: boolean;
  emptyTitle: string;
  emptyDescription: string;
}

export function FeedView({ types, showSeverity = false, emptyTitle, emptyDescription }: FeedViewProps) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const allTypes = useMemo<ItemType[]>(
    () =>
      types.length
        ? types
        : ["news", "model_release", "tool", "research", "github_repo", "github_issue", "bug", "vulnerability", "incident", "devops"],
    [types],
  );
  const state = useMemo(() => parseFeedState(params, allTypes), [params, allTypes]);
  // Relative ranges ("last 24h") are anchored to when the page opened, rounded to the minute,
  // so the query key stays stable across renders.
  const [minute] = useState(() => Math.floor(Date.now() / 60_000) * 60_000);
  const filters = useMemo(() => toApiFilters(state, types, minute), [state, types, minute]);
  const news = useNews(filters);

  // URL updates are asynchronous, so rapid successive changes must build on the latest *intended*
  // state rather than the last rendered one (otherwise one click can overwrite another).
  const latest = useRef(state);
  useEffect(() => {
    latest.current = state;
  }, [state]);
  const update = useCallback(
    (patch: Partial<FeedState>) => {
      latest.current = { ...latest.current, ...patch };
      const next = serializeFeedState(latest.current);
      router.replace(next ? `${pathname}?${next}` : pathname, { scroll: false });
    },
    [pathname, router],
  );

  const filtered = activeFilterCount(state) > 0 || !!state.q;

  return (
    <section aria-label="Feed">
      <FeedFilters state={state} onChange={update} typeOptions={allTypes} showSeverity={showSeverity} />
      {news.isLoading ? (
        <ListSkeleton />
      ) : news.isError ? (
        <ErrorState error={news.error} onRetry={() => news.refetch()} />
      ) : !news.data || news.data.items.length === 0 ? (
        filtered ? (
          <EmptyState
            icon={SearchX}
            title="No items match these filters"
            description="Try a broader search, a longer date range, or fewer filters."
          />
        ) : (
          <EmptyState title={emptyTitle} description={emptyDescription} />
        )
      ) : (
        <>
          <p className="mb-3 text-xs text-muted-foreground" aria-live="polite">
            <span className="tabular">{news.data.total.toLocaleString("en")}</span> item{news.data.total === 1 ? "" : "s"}
            {news.isFetching && " · updating…"}
          </p>
          <div className="grid gap-3">
            {news.data.items.map((a) => (
              <ArticleCard key={a.id} article={a} showType={allTypes.length > 1} />
            ))}
          </div>
          <Pagination
            page={news.data.page}
            pages={news.data.pages}
            total={news.data.total}
            pageSize={PAGE_SIZE}
            onChange={(page) => {
              update({ page });
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
          />
        </>
      )}
    </section>
  );
}
