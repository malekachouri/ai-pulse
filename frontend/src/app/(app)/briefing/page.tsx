"use client";

import {
  AlertOctagon,
  CheckCircle2,
  ExternalLink,
  GitCompareArrows,
  Loader2,
  RefreshCw,
  Settings2,
  Sparkles,
  Star,
  Sunrise,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { SeverityBadge } from "@/components/feed/badges";
import { PageHeader } from "@/components/layout/page-header";
import { KevBadge, StateBadge } from "@/components/radar/shared";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/lib/auth";
import { useBriefingByDate, useBriefings, useGenerateBriefing, useLatestBriefing } from "@/lib/queries";
import type { Briefing, BriefingMeta, BriefingSectionItem, Severity } from "@/lib/types";
import { cn, formatDateTime, safeUrl, titleCase } from "@/lib/utils";

/** Display order = the briefing's structure: 1 executive summary, 2-8 facts, 9 changes, 10 learning. */
const SECTIONS: { key: string; title: string; empty: string }[] = [
  { key: "top_ai", title: "Most important AI news", empty: "No major AI news in this period." },
  { key: "model_releases", title: "New model releases", empty: "No new model releases from tracked providers." },
  { key: "new_tools", title: "New tools & frameworks", empty: "No new tools or frameworks." },
  { key: "research", title: "Research papers", empty: "No notable papers." },
  { key: "bugs", title: "Important bugs", empty: "No important bugs with a documented severity." },
  { key: "vulnerabilities", title: "Critical vulnerabilities", empty: "No critical or high vulnerabilities, and nothing newly exploited." },
  { key: "incidents", title: "Cloud & infrastructure incidents", empty: "No provider incidents in this period." },
  { key: "devops", title: "DevOps & cloud updates", empty: "No DevOps or cloud updates." },
  { key: "changes", title: "What changed since the previous briefing", empty: "Nothing changed." },
  { key: "learning", title: "Recommended learning", empty: "No learning suggestions for this period." },
];
const WIDE = new Set(["top_ai", "changes"]);
const FREQ: Record<string, string> = { daily: "Daily", weekdays: "Weekdays", weekly: "Weekly", off: "On demand" };

function Title({ item }: { item: BriefingSectionItem }) {
  const href = item.url?.startsWith("/") ? null : safeUrl(item.url);
  if (item.url?.startsWith("/") && !item.url.startsWith("//"))
    return (
      <Link href={item.url} className="font-medium hover:text-primary">
        {item.title}
      </Link>
    );
  return href ? (
    <a href={href} target="_blank" rel="noopener noreferrer" className="group inline-flex items-start gap-1 font-medium hover:text-primary">
      {item.title}
      <ExternalLink className="mt-1 size-3 shrink-0 opacity-60" />
    </a>
  ) : (
    <span className="font-medium">{item.title}</span>
  );
}

const CHANGE_ICON = { resolved: CheckCircle2, exploited: AlertOctagon, followed: Star, count: GitCompareArrows } as const;

function Item({ item, section }: { item: BriefingSectionItem; section: string }) {
  const ChangeIcon = section === "changes" ? CHANGE_ICON[item.kind ?? "count"] : null;
  return (
    <li className="flex gap-2 text-sm">
      {ChangeIcon && (
        <ChangeIcon
          className={cn(
            "mt-0.5 size-4 shrink-0",
            item.kind === "exploited" ? "text-red-600 dark:text-red-400" : item.kind === "resolved" ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground",
          )}
          aria-hidden
        />
      )}
      <div className="min-w-0">
        <Title item={item} />
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
          {item.provider && <span className="font-semibold">{item.provider}</span>}
          {item.state && <StateBadge i={{ state: item.state }} />}
          {item.last_verified_at && <span>verified {formatDateTime(item.last_verified_at)}</span>}
          {item.severity && item.severity !== "unknown" && item.severity_basis && (
            <SeverityBadge severity={item.severity as Severity} basis={item.severity_basis} />
          )}
          {item.cvss != null && <span>CVSS {item.cvss}</span>}
          {item.known_exploited && <KevBadge />}
          {section !== "changes" && section !== "learning" && item.source && <span>{item.source}</span>}
          {item.importance != null && <span>importance {Math.round(item.importance)}</span>}
        </div>
        {item.summary && (
          <p className="mt-0.5 text-muted-foreground">
            {item.summary_is_ai && (
              <span className="mr-1 text-[10px] font-semibold uppercase text-violet-700 dark:text-violet-300">AI</span>
            )}
            {item.summary}
          </p>
        )}
        {item.why_for_you && item.why_for_you.length > 0 && (
          <p className="mt-0.5 text-[11px] text-primary">{item.why_for_you.join(" · ")}</p>
        )}
      </div>
    </li>
  );
}

function Section({ name, title, empty, value }: { name: string; title: string; empty: string; value: unknown }) {
  const items = Array.isArray(value) ? (value as BriefingSectionItem[]) : null;
  return (
    <Card className={cn(WIDE.has(name) && "md:col-span-2")}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2">
          {title}
          {items && items.length > 0 && <span className="tabular text-xs font-normal text-muted-foreground">{items.length}</span>}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {typeof value === "string" ? (
          <p className="text-sm leading-relaxed">{value}</p>
        ) : !items?.length ? (
          <p className="text-sm text-muted-foreground">{empty}</p>
        ) : (
          <ul className="space-y-3">
            {items.map((item, i) => (
              <Item key={`${item.article_id ?? ""}-${i}`} item={item} section={name} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function BriefingView({ b }: { b: Briefing }) {
  const meta = b.sections.meta as BriefingMeta | undefined;
  const known = new Set([...SECTIONS.map((s) => s.key), "meta"]);
  const extra = Object.keys(b.sections).filter((k) => !known.has(k));
  return (
    <div className="space-y-4">
      <Card className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-brand-blue/10 via-transparent to-brand-violet/10" />
        <CardContent className="relative pt-5">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Badge variant={b.llm_model ? "violet" : "secondary"}>
              <Sparkles /> {b.llm_model ? "AI-generated summary" : "Automatic summary (no LLM)"}
            </Badge>
            {b.user_id ? <Badge variant="secondary">Personalised</Badge> : <Badge variant="outline">General edition</Badge>}
            {meta && <Badge variant="outline">{FREQ[meta.frequency] ?? meta.frequency}</Badge>}
            <span className="text-xs text-muted-foreground">
              {b.briefing_date} · covers {formatDateTime(b.period_start)} → {formatDateTime(b.period_end)}
              {b.llm_model && ` · ${b.llm_provider}/${b.llm_model}`}
            </span>
          </div>
          <h2 className="mb-2 text-base font-semibold">Executive summary</h2>
          <p className="text-sm leading-relaxed">{b.executive_summary ?? "No summary available."}</p>
          {meta && (
            <p className="mt-3 text-xs text-muted-foreground">
              {meta.interests.length ? (
                <>Ranked for your interests: {meta.interests.map(titleCase).join(", ")}</>
              ) : (
                <>
                  No interests selected —{" "}
                  <Link href="/settings#preferences" className="text-primary underline underline-offset-2">
                    choose some
                  </Link>{" "}
                  to personalise the ranking
                </>
              )}
              {meta.followed_count > 0 && ` · ${meta.followed_count} followed items boosted`}
              {meta.previous_briefing_date && ` · compared with ${meta.previous_briefing_date}`}
            </p>
          )}
          <p className="mt-2 text-[11px] text-muted-foreground">
            Sections list collected items only, each linked to its source. Only the executive summary and item summaries marked AI
            are generated.
          </p>
        </CardContent>
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        {SECTIONS.filter((s) => s.key in b.sections || s.key !== "devops").map((s) => (
          <Section key={s.key} name={s.key} title={s.title} empty={s.empty} value={b.sections[s.key]} />
        ))}
        {extra.map((k) => (
          <Section key={k} name={k} title={titleCase(k)} empty="Nothing in this period." value={b.sections[k]} />
        ))}
      </div>
    </div>
  );
}

function BriefingContent() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const date = params.get("date");
  const latest = useLatestBriefing();
  const byDate = useBriefingByDate(date);
  const history = useBriefings();
  const current = date ? byDate : latest;
  const b = current.data;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_260px]">
      <div>
        {current.isLoading ? (
          <ListSkeleton rows={3} />
        ) : current.isError ? (
          <ErrorState error={current.error} onRetry={() => current.refetch()} />
        ) : !b ? (
          <EmptyState
            icon={Sunrise}
            title="No briefing generated yet"
            description={
              <>
                Briefings are generated on your schedule from collected items. Choose your interests, frequency, delivery time and
                timezone in{" "}
                <Link href="/settings#preferences" className="text-primary underline underline-offset-2">
                  Settings
                </Link>
                , or use Generate now.
              </>
            }
          />
        ) : (
          <BriefingView b={b} />
        )}
      </div>
      <Card className="h-fit">
        <CardHeader>
          <CardTitle>Previous briefings</CardTitle>
        </CardHeader>
        <CardContent>
          {history.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : !history.data?.length ? (
            <p className="text-sm text-muted-foreground">No history yet.</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {history.data.map((h) => {
                const active = b?.briefing_date === h.briefing_date && (b?.user_id != null) === h.personalized;
                return (
                  <li key={h.id}>
                    <button
                      type="button"
                      onClick={() => router.replace(`${pathname}?date=${h.briefing_date}`, { scroll: false })}
                      className={cn(
                        "flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left hover:bg-accent",
                        active && "bg-accent font-medium",
                      )}
                      aria-current={active ? "true" : undefined}
                    >
                      <span>{h.briefing_date}</span>
                      {h.personalized ? <Badge variant="secondary">Yours</Badge> : <Badge variant="outline">General</Badge>}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function BriefingPage() {
  const { status } = useAuth();
  const gen = useGenerateBriefing();
  const router = useRouter();
  const action =
    status === "authenticated" ? (
      <div className="flex gap-2">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/settings#preferences">
            <Settings2 /> Schedule
          </Link>
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => gen.mutate(undefined, { onSuccess: () => router.replace("/briefing", { scroll: false }) })}
          disabled={gen.isPending}
        >
          {gen.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />} Generate now
        </Button>
      </div>
    ) : undefined;

  return (
    <>
      <PageHeader
        title="Daily Briefing"
        description="Your personalised digest: what matters for your interests, what changed since last time, and what to learn next. Every item links to its original source."
        icon={Sunrise}
        actions={action}
      />
      <Suspense fallback={<ListSkeleton rows={3} />}>
        <BriefingContent />
      </Suspense>
    </>
  );
}
