"use client";

import { ArrowUpRight } from "lucide-react";
import Link from "next/link";

import { ImportanceMeter, SeverityBadge } from "@/components/feed/badges";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Article } from "@/lib/types";
import { safeUrl, timeAgo } from "@/lib/utils";

export function CompactArticleList({
  title,
  items,
  loading,
  href,
  empty,
}: {
  title: string;
  items: Article[] | undefined;
  loading?: boolean;
  href: string;
  empty: string;
}) {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <Link href={href} className="inline-flex items-center gap-0.5 text-xs text-primary hover:underline">
          View all <ArrowUpRight className="size-3" />
        </Link>
      </CardHeader>
      <CardContent className="flex-1">
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }, (_, i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        ) : !items?.length ? (
          <p className="py-6 text-center text-sm text-muted-foreground">{empty}</p>
        ) : (
          <ul className="divide-y">
            {items.map((a) => {
              const url = safeUrl(a.url);
              return (
                <li key={a.id} className="py-2.5 first:pt-0 last:pb-0">
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="line-clamp-2 text-sm font-medium leading-snug hover:text-primary"
                  >
                    {a.title}
                  </a>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                    <span className="truncate">{a.source.name}</span>
                    <span>·</span>
                    <span>{timeAgo(a.published_at ?? a.collected_at)}</span>
                    {a.severity && a.severity !== "unknown" && <SeverityBadge severity={a.severity} basis={a.severity_basis} />}
                    {a.importance_score != null && <ImportanceMeter score={a.importance_score} compact />}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
