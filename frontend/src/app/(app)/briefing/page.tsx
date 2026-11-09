"use client";

import { ExternalLink, Sparkles, Sunrise } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/layout/page-header";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useBriefings, useLatestBriefing } from "@/lib/queries";
import type { BriefingSectionItem } from "@/lib/types";
import { formatDateTime, safeUrl, titleCase } from "@/lib/utils";

const SECTION_TITLES: Record<string, string> = {
  top_ai: "Most important AI news",
  model_releases: "New model releases",
  new_tools: "New tools & frameworks",
  research: "Research papers",
  bugs: "Important bugs",
  vulnerabilities: "Critical vulnerabilities",
  incidents: "Cloud & infrastructure incidents",
  changes: "What changed since the previous briefing",
  learning: "Recommended learning",
};

function Section({ name, value }: { name: string; value: BriefingSectionItem[] | string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{SECTION_TITLES[name] ?? titleCase(name)}</CardTitle>
      </CardHeader>
      <CardContent>
        {typeof value === "string" ? (
          <p className="text-sm leading-relaxed">{value}</p>
        ) : value.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing notable in this period.</p>
        ) : (
          <ul className="space-y-3">
            {value.map((item, i) => {
              const href = safeUrl(item.url);
              return (
                <li key={item.article_id ?? i} className="text-sm">
                  {href ? (
                    <a href={href} target="_blank" rel="noopener noreferrer" className="group inline-flex items-start gap-1 font-medium hover:text-primary">
                      {item.title}
                      <ExternalLink className="mt-1 size-3 shrink-0 opacity-60" />
                    </a>
                  ) : (
                    <span className="font-medium">{item.title}</span>
                  )}
                  {item.summary && <p className="mt-0.5 text-muted-foreground">{item.summary}</p>}
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export default function BriefingPage() {
  const latest = useLatestBriefing();
  const history = useBriefings();
  const b = latest.data;

  return (
    <>
      <PageHeader
        title="Daily Briefing"
        description="A daily digest of what matters for your interests. Every item links to its original source."
        icon={Sunrise}
      />
      {latest.isLoading ? (
        <ListSkeleton rows={3} />
      ) : latest.isError ? (
        <ErrorState error={latest.error} onRetry={() => latest.refetch()} />
      ) : !b ? (
        <EmptyState
          icon={Sunrise}
          title="No briefing generated yet"
          description={
            <>
              Briefings are generated on a schedule from collected items once ingestion and the AI engine are enabled. You
              can already choose your interests and delivery time in{" "}
              <Link href="/settings#preferences" className="text-primary hover:underline">
                Settings
              </Link>
              .
            </>
          }
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_260px]">
          <div className="space-y-4">
            <Card className="relative overflow-hidden">
              <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-brand-blue/10 via-transparent to-brand-violet/10" />
              <CardContent className="relative pt-5">
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <Badge variant="violet">
                    <Sparkles /> AI-generated
                  </Badge>
                  {b.user_id && <Badge variant="secondary">Personalised</Badge>}
                  <span className="text-xs text-muted-foreground">
                    {formatDateTime(b.period_start)} → {formatDateTime(b.period_end)}
                    {b.llm_model && ` · ${b.llm_provider}/${b.llm_model}`}
                  </span>
                </div>
                <h2 className="mb-2 text-base font-semibold">Executive summary</h2>
                <p className="text-sm leading-relaxed">{b.executive_summary ?? "No summary available."}</p>
              </CardContent>
            </Card>
            <div className="grid gap-4 md:grid-cols-2">
              {Object.entries(b.sections).map(([name, value]) => (
                <Section key={name} name={name} value={value} />
              ))}
            </div>
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
                <ul className="space-y-2 text-sm">
                  {history.data.map((h) => (
                    <li key={h.id} className="flex items-center justify-between gap-2">
                      <span>{h.briefing_date}</span>
                      {h.personalized && <Badge variant="secondary">Yours</Badge>}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
