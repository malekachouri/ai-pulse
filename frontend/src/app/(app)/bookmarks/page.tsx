"use client";

import { Bookmark } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ArticleCard } from "@/components/feed/article-card";
import { Pagination } from "@/components/feed/pagination";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState, ErrorState, ListSkeleton, SignInRequired } from "@/components/states/states";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { useBookmarks } from "@/lib/queries";

export default function BookmarksPage() {
  const { status } = useAuth();
  const [page, setPage] = useState(1);
  const q = useBookmarks(page);

  return (
    <>
      <PageHeader title="Bookmarks" description="Items you saved for later." icon={Bookmark} />
      {status === "loading" ? (
        <ListSkeleton rows={2} />
      ) : status === "anonymous" ? (
        <SignInRequired what="bookmarks" />
      ) : q.isLoading ? (
        <ListSkeleton />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : !q.data?.items.length ? (
        <EmptyState
          icon={Bookmark}
          title="No bookmarks yet"
          description="Use the bookmark button on any item to save it here."
          action={
            <Button asChild variant="outline" size="sm">
              <Link href="/news">Browse AI news</Link>
            </Button>
          }
        />
      ) : (
        <>
          <div className="grid gap-3">
            {q.data.items.map((b) => (
              <div key={b.id}>
                <ArticleCard article={b.article} />
                {b.note && <p className="mt-1.5 px-1 text-xs text-muted-foreground">Note: {b.note}</p>}
              </div>
            ))}
          </div>
          <Pagination page={q.data.page} pages={q.data.pages} total={q.data.total} pageSize={q.data.page_size} onChange={setPage} />
        </>
      )}
    </>
  );
}
