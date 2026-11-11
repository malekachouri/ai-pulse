"use client";

import { BookOpen, ExternalLink, GraduationCap, Lightbulb, Loader2, RefreshCw, Sparkles } from "lucide-react";
import Link from "next/link";

import { ArticleCard } from "@/components/feed/article-card";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState, ErrorState, ListSkeleton, SignInRequired } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/lib/auth";
import { useGenerateLessons, useLessons, useRecommendations } from "@/lib/queries";
import type { Lesson } from "@/lib/types";
import { formatDateTime, safeUrl } from "@/lib/utils";

function LessonCard({ lesson }: { lesson: Lesson }) {
  return (
    <Card>
      <CardContent className="space-y-3 pt-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary" className="gap-1">
            <Sparkles className="size-3" aria-hidden /> AI-generated
          </Badge>
          {lesson.personal_reason && <span className="text-xs text-muted-foreground">{lesson.personal_reason}</span>}
        </div>
        <h3 className="text-base font-semibold leading-snug">{lesson.title}</h3>
        <p className="text-sm leading-relaxed">{lesson.explanation}</p>
        {lesson.key_points.length > 0 && (
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {lesson.key_points.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        )}
        {lesson.why_it_matters && (
          <p className="text-sm">
            <span className="font-semibold">Why it matters: </span>
            {lesson.why_it_matters}
          </p>
        )}
        {lesson.try_it && (
          <p className="flex gap-2 rounded-md bg-primary/10 px-3 py-2 text-sm">
            <Lightbulb className="mt-0.5 size-4 shrink-0 text-primary-tint-fg" aria-hidden />
            <span>
              <span className="font-semibold">Try it: </span>
              {lesson.try_it}
            </span>
          </p>
        )}
        {lesson.resources.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Official documentation</p>
            <ul className="mt-1 space-y-1 text-sm">
              {lesson.resources.map((r) => (
                <li key={r.url}>
                  <a href={safeUrl(r.url)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary underline underline-offset-2">
                    <BookOpen className="size-3.5" aria-hidden /> {r.title}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
        <p className="border-t pt-2 text-xs text-muted-foreground">
          Based on{" "}
          <a href={safeUrl(lesson.source.url)} target="_blank" rel="noopener noreferrer" className="text-primary underline underline-offset-2">
            {lesson.source.title}
          </a>{" "}
          ({lesson.source.source}). Written by {lesson.provider} / {lesson.model}, {formatDateTime(lesson.created_at)}.
          {lesson.unsupported_claims_removed.length > 0 && ` ${lesson.unsupported_claims_removed.length} unsupported claim(s) removed.`}
        </p>
      </CardContent>
    </Card>
  );
}

function Lessons() {
  const q = useLessons();
  const gen = useGenerateLessons();
  const d = q.data;
  return (
    <section aria-labelledby="lessons-title" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="lessons-title" className="text-lg font-semibold">Today&apos;s lessons</h2>
          <p className="text-sm text-muted-foreground">Short technical lessons from today&apos;s most important news and papers, for what you follow.</p>
        </div>
        {d && d.status !== "disabled" && (
          <Button variant="outline" size="sm" onClick={() => gen.mutate()} disabled={gen.isPending}>
            {gen.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />} {d.status === "ready" ? "Regenerate" : "Generate today's lessons"}
          </Button>
        )}
      </div>
      {q.isLoading ? (
        <ListSkeleton rows={2} />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : d?.status === "disabled" ? (
        <EmptyState
          icon={Sparkles}
          title="AI lessons are not enabled"
          description="An administrator can configure an LLM provider (LLM_PROVIDER and LLM_MODEL). Recommendations below work without it."
        />
      ) : !d?.lessons.length ? (
        <EmptyState icon={GraduationCap} title="No lessons yet today" description="Generate them from today's important items." />
      ) : (
        <>
          <p className="text-xs text-muted-foreground">{d.ai_generated_notice}</p>
          <div className="grid gap-3 lg:grid-cols-2">
            {d.lessons.map((l) => (
              <LessonCard key={l.id} lesson={l} />
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function Recommended() {
  const q = useRecommendations();
  const d = q.data;
  return (
    <section aria-labelledby="recs-title" className="space-y-3">
      <div>
        <h2 id="recs-title" className="text-lg font-semibold">What to learn next</h2>
        <p className="text-sm text-muted-foreground">
          Collected items and official documentation picked from what you follow, read and bookmark, with the reason for each.
        </p>
      </div>
      {q.isLoading ? (
        <ListSkeleton rows={3} />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : !d || (!d.items.length && !d.resources.length) ? (
        <EmptyState
          icon={GraduationCap}
          title="Nothing to recommend yet"
          description={d?.note ?? "Follow technologies or read items to get recommendations."}
          action={
            <Button asChild variant="outline" size="sm">
              <Link href="/settings#preferences">Choose what you follow</Link>
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
          <div className="space-y-3">
            {d.items.length === 0 && d.note && <p className="text-sm text-muted-foreground">{d.note}</p>}
            {d.items.map((i) => (
              <div key={i.article.id} className="space-y-1.5">
                <ul className="flex flex-wrap gap-1.5" aria-label="Why it is recommended">
                  {i.reasons.map((r) => (
                    <li key={r} className="rounded-md bg-primary/10 px-2 py-0.5 text-xs text-primary-tint-fg">
                      {r}
                    </li>
                  ))}
                </ul>
                <ArticleCard article={i.article} />
              </div>
            ))}
          </div>
          {d.resources.length > 0 && (
            <Card className="h-fit">
              <CardContent className="space-y-3 pt-5">
                <h3 className="text-sm font-semibold">Official documentation for you</h3>
                <ul className="space-y-2.5">
                  {d.resources.map((r) => (
                    <li key={r.url} className="text-sm">
                      <a href={safeUrl(r.url)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-medium text-primary underline underline-offset-2">
                        {r.title} <ExternalLink className="size-3" aria-hidden />
                      </a>
                      <p className="text-xs text-muted-foreground">{r.reason}</p>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </section>
  );
}

export default function LearnPage() {
  const { status } = useAuth();
  return (
    <>
      <PageHeader
        title="Learn"
        description="Lessons from today's important items and recommendations for what to learn next."
        icon={GraduationCap}
      />
      {status === "loading" ? (
        <ListSkeleton rows={2} />
      ) : status === "anonymous" ? (
        <SignInRequired what="learning plan" description="Lessons and recommendations are personal to your account." />
      ) : (
        <div className="space-y-10">
          <Lessons />
          <Recommended />
        </div>
      )}
    </>
  );
}
