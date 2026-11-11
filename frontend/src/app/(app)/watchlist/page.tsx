"use client";

import { Bug, Cpu, ExternalLink, Eye, GitBranch, Layers, Settings2, ShieldAlert, type LucideIcon } from "lucide-react";
import Link from "next/link";

import { ArticleCard } from "@/components/feed/article-card";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState, ErrorState, ListSkeleton, SignInRequired } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/lib/auth";
import { useWatchlist } from "@/lib/queries";
import type { WatchEntry } from "@/lib/types";
import { formatDateTime, safeUrl } from "@/lib/utils";

const KIND: Record<WatchEntry["kind"], { label: string; icon: LucideIcon }> = {
  technology: { label: "Technology", icon: Layers },
  provider: { label: "Provider", icon: Cpu },
  repository: { label: "Repository", icon: GitBranch },
};

function Entry({ e }: { e: WatchEntry }) {
  const k = KIND[e.kind];
  const id = `watch-${e.kind}-${e.term.replace(/[^A-Za-z0-9]+/g, "-").toLowerCase()}`;
  return (
    <section aria-labelledby={id}>
      <Card>
        <CardContent className="space-y-3 pt-5">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <h2 id={id} className="flex items-center gap-1.5 text-base font-semibold">
              <k.icon className="size-4 text-primary" aria-hidden /> {e.term}
            </h2>
            <Badge variant="outline">{k.label}</Badge>
            <span className="text-xs text-muted-foreground">
              {e.new_this_week} new this week · {e.total} in 30 days
              {e.vulnerabilities > 0 && (
                <>
                  {" · "}
                  <ShieldAlert className="inline size-3" aria-hidden /> {e.vulnerabilities} vulnerabilit{e.vulnerabilities === 1 ? "y" : "ies"}
                </>
              )}
              {e.open_critical_bugs ? (
                <>
                  {" · "}
                  <Bug className="inline size-3" aria-hidden /> {e.open_critical_bugs} open critical bug{e.open_critical_bugs === 1 ? "" : "s"}
                </>
              ) : null}
            </span>
          </div>
          {e.latest_release && (
            <p className="rounded-md bg-primary/10 px-3 py-2 text-sm">
              <span className="font-semibold">Latest release: </span>
              <a href={safeUrl(e.latest_release.url)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary-tint-fg underline underline-offset-2">
                {e.latest_release.version ?? e.latest_release.title} <ExternalLink className="size-3" aria-hidden />
              </a>
              <span className="text-xs text-muted-foreground">
                {" "}
                · {e.latest_release.source}
                {e.latest_release.published_at && ` · ${formatDateTime(e.latest_release.published_at)}`}
              </span>
            </p>
          )}
          {e.items.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing collected about {e.term} in the last 30 days.</p>
          ) : (
            <div className="space-y-2">
              {e.items.map((a) => (
                <ArticleCard key={a.id} article={a} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </section>
  );
}

export default function WatchlistPage() {
  const { status } = useAuth();
  const q = useWatchlist();
  const d = q.data;
  return (
    <>
      <PageHeader
        title="Watchlist"
        description="Everything new about the models, frameworks, providers and repositories you follow, linked to the original sources. New releases are also sent as notifications."
        icon={Eye}
        actions={
          status === "authenticated" ? (
            <Button asChild variant="outline" size="sm">
              <Link href="/settings#preferences">
                <Settings2 /> Edit what you follow
              </Link>
            </Button>
          ) : undefined
        }
      />
      {status === "loading" || (status === "authenticated" && q.isLoading) ? (
        <ListSkeleton rows={3} />
      ) : status === "anonymous" ? (
        <SignInRequired what="watchlist" description="Your watchlist is built from what you follow." />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : !d?.entries.length ? (
        <EmptyState
          icon={Eye}
          title="Your watchlist is empty"
          description={d?.note ?? "Follow technologies, providers or repositories to build it."}
          action={
            <Button asChild variant="outline" size="sm">
              <Link href="/settings#preferences">Choose what you follow</Link>
            </Button>
          }
        />
      ) : (
        <div className="space-y-4">
          <p className="text-xs text-muted-foreground">{d.method}</p>
          {d.entries.map((e) => (
            <Entry key={`${e.kind}:${e.term}`} e={e} />
          ))}
        </div>
      )}
    </>
  );
}
