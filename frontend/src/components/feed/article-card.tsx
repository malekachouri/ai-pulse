"use client";

import { Bookmark, BookmarkCheck, Circle, CircleCheck, ExternalLink, ScanSearch, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AnalysisSheet } from "@/components/feed/analysis-sheet";

import { ImportanceMeter, ItemTypeBadge, SeverityBadge, VerificationBadge } from "@/components/feed/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { useAuth } from "@/lib/auth";
import { useToggleBookmark, useToggleRead } from "@/lib/queries";
import type { Article } from "@/lib/types";
import { cn, formatDateTime, safeUrl, timeAgo } from "@/lib/utils";

export function ArticleCard({ article, showType = true }: { article: Article; showType?: boolean }) {
  const { status } = useAuth();
  const router = useRouter();
  const bookmark = useToggleBookmark();
  const read = useToggleRead();
  const authed = status === "authenticated";
  const href = safeUrl(article.url);
  const published = article.published_at;

  const requireAuth = (fn: () => void) => () => (authed ? fn() : router.push("/login"));
  const [explain, setExplain] = useState(false);

  return (
    <article
      className={cn(
        "group relative rounded-xl border bg-card p-4 shadow-sm transition-all hover:border-primary/40 hover:shadow-md sm:p-5",
        article.is_read && "opacity-80",
      )}
      aria-label={article.title}
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5 text-xs text-muted-foreground">
        {!article.is_read && authed && <span className="size-2 rounded-full bg-primary" role="img" aria-label="Unread" />}
        <span className="font-medium text-foreground/90">{article.source.name}</span>
        <VerificationBadge status={article.verification_status} />
        <span aria-hidden>·</span>
        <Tooltip
          content={
            <>
              Published: {published ? formatDateTime(published) : "not provided by source"}
              <br />
              Collected: {formatDateTime(article.collected_at)}
            </>
          }
        >
          <time dateTime={published ?? article.collected_at} className="cursor-default">
            {published ? timeAgo(published) : `collected ${timeAgo(article.collected_at)}`}
          </time>
        </Tooltip>
      </div>

      <h2 className="mt-2 text-[15px] font-semibold leading-snug sm:text-base">
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="outline-none hover:text-primary focus-visible:underline"
            onClick={() => authed && !article.is_read && read.mutate({ id: article.id, read: true })}
          >
            {article.title}
          </a>
        ) : (
          article.title
        )}
      </h2>

      {article.description && (
        <p className="mt-1.5 line-clamp-3 text-sm leading-relaxed text-muted-foreground">{article.description}</p>
      )}

      {article.ai_summary && (
        <div className="mt-3 rounded-lg border border-brand-violet/25 bg-brand-violet/[0.06] p-3">
          <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-violet-700 dark:text-violet-300">
            <Sparkles className="size-3.5" /> AI-generated summary
            <span className="font-normal normal-case tracking-normal text-muted-foreground">
              · {article.ai_summary.provider}/{article.ai_summary.model}
            </span>
          </p>
          <p className="text-sm leading-relaxed">{article.ai_summary.short}</p>
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {showType && <ItemTypeBadge type={article.item_type} />}
        {article.severity && article.severity !== "unknown" && (
          <SeverityBadge severity={article.severity} basis={article.severity_basis} />
        )}
        {article.categories.map((c) => (
          <Badge key={c.id} variant="outline">
            {c.name}
          </Badge>
        ))}
      </div>

      <div className="mt-3 flex items-center justify-between gap-2 border-t pt-3">
        <ImportanceMeter score={article.importance_score} />
        <div className="flex items-center gap-0.5">
          <Tooltip content="Importance breakdown and AI analysis">
            <Button variant="ghost" size="sm" onClick={() => setExplain(true)} aria-label="Explain this item">
              <ScanSearch /> <span className="hidden sm:inline">Explain</span>
            </Button>
          </Tooltip>
          <Tooltip content={article.is_read ? "Mark as unread" : "Mark as read"}>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-pressed={article.is_read}
              aria-label={article.is_read ? "Mark as unread" : "Mark as read"}
              onClick={requireAuth(() => read.mutate({ id: article.id, read: !article.is_read }))}
            >
              {article.is_read ? <CircleCheck className="text-emerald-600 dark:text-emerald-400" /> : <Circle />}
            </Button>
          </Tooltip>
          <Tooltip content={article.is_bookmarked ? "Remove bookmark" : "Bookmark"}>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-pressed={article.is_bookmarked}
              aria-label={article.is_bookmarked ? "Remove bookmark" : "Bookmark"}
              onClick={requireAuth(() => bookmark.mutate({ id: article.id, on: !article.is_bookmarked }))}
            >
              {article.is_bookmarked ? <BookmarkCheck className="text-primary" /> : <Bookmark />}
            </Button>
          </Tooltip>
          {href && (
            <Button asChild variant="ghost" size="sm" className="text-primary">
              <a href={href} target="_blank" rel="noopener noreferrer">
                Source <ExternalLink />
              </a>
            </Button>
          )}
        </div>
      </div>
      {explain && <AnalysisSheet article={article} open={explain} onOpenChange={setExplain} />}
    </article>
  );
}
