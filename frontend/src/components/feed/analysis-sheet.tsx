"use client";

import { BookOpen, ExternalLink, Gauge, Info, Sparkles, Tags } from "lucide-react";

import { ReleaseChanges } from "@/components/intel/release-changes";
import { ErrorState } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useArticleAnalysis } from "@/lib/queries";
import type { Article } from "@/lib/types";
import { formatDateTime, safeUrl, titleCase } from "@/lib/utils";

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-1.5">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      <div className="text-sm leading-relaxed">{children}</div>
    </section>
  );
}

export function AnalysisSheet({ article, open, onOpenChange }: { article: Article; open: boolean; onOpenChange: (v: boolean) => void }) {
  const q = useArticleAnalysis(open ? article.id : null);
  const d = q.data;
  const s = d?.summary;
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" title={`Analysis: ${article.title}`} className="w-[min(100vw,560px)] max-w-none overflow-y-auto bg-background p-0">
        <div className="space-y-6 p-5 pr-10">
          <div>
            <p className="text-xs text-muted-foreground">{article.source.name}</p>
            <h2 className="mt-1 text-base font-semibold leading-snug">{article.title}</h2>
            <a href={safeUrl(article.url)} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-xs text-primary hover:underline">
              Original source <ExternalLink className="size-3" />
            </a>
          </div>

          {q.isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-20" />
              <Skeleton className="h-40" />
            </div>
          ) : q.isError ? (
            <ErrorState error={q.error} onRetry={() => q.refetch()} />
          ) : d ? (
            <>
              {d.changes && <ReleaseChanges c={d.changes} />}
              {d.importance && (
                <section className="rounded-xl border bg-card p-4">
                  <div className="flex items-baseline justify-between">
                    <h3 className="flex items-center gap-1.5 text-sm font-semibold">
                      <Gauge className="size-4 text-primary" /> AI Pulse importance
                    </h3>
                    <p className="tabular text-2xl font-semibold">
                      {Math.round(d.importance.score)}
                      <span className="text-sm font-normal text-muted-foreground">/100</span>
                    </p>
                  </div>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">{d.importance.label}</p>
                  <ul className="mt-3 space-y-2">
                    {d.importance.factors.map((f) => (
                      <li key={f.name} className="text-xs">
                        <div className="flex justify-between gap-2">
                          <span className="font-medium">{titleCase(f.name)}</span>
                          <span className="tabular text-muted-foreground">+{f.contribution.toFixed(1)}</span>
                        </div>
                        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                          <div className="h-full rounded-full bg-[var(--chart-series)]" style={{ width: `${Math.round(f.value * 100)}%` }} />
                        </div>
                        <p className="mt-0.5 text-muted-foreground">{f.reason}</p>
                      </li>
                    ))}
                  </ul>
                  {d.importance.excluded.length > 0 && (
                    <p className="mt-2 text-[11px] text-muted-foreground">Not applicable here: {d.importance.excluded.map(titleCase).join(", ")}.</p>
                  )}
                  {d.importance.personal_score != null && d.importance.personal_reasons.length > 0 && (
                    <p className="mt-2 rounded-md bg-primary/10 px-2 py-1.5 text-xs">
                      For you: <strong>{Math.round(d.importance.personal_score)}</strong> — {d.importance.personal_reasons.join("; ")}
                    </p>
                  )}
                </section>
              )}

              <section className="rounded-xl border border-brand-violet/25 bg-brand-violet/[0.05] p-4">
                <p className="mb-3 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-violet-700 dark:text-violet-300">
                  <Sparkles className="size-3.5" /> AI-generated analysis
                  {d.summary_status.model && (
                    <span className="font-normal normal-case tracking-normal text-muted-foreground">
                      · {d.summary_status.provider}/{d.summary_status.model} · {formatDateTime(d.summary_status.generated_at)}
                    </span>
                  )}
                </p>
                {!s ? (
                  <p className="flex items-start gap-2 text-sm text-muted-foreground">
                    <Info className="mt-0.5 size-4 shrink-0" />
                    {d.summary_status.status === "disabled"
                      ? "AI summaries are not enabled on this server (no LLM provider configured). The importance score, keywords and entities above are computed without AI."
                      : d.summary_status.status === "failed"
                        ? `The AI analysis failed and will be retried: ${d.summary_status.error ?? "unknown error"}`
                        : "This item is queued for AI analysis (most important items are analysed first)."}
                  </p>
                ) : (
                  <div className="space-y-4">
                    <p className="text-sm font-medium leading-relaxed">{s.short_summary}</p>
                    {s.what_happened && <Block title="What happened">{s.what_happened}</Block>}
                    {s.why_it_matters && <Block title="Why it matters">{s.why_it_matters}</Block>}
                    {s.who_is_affected && <Block title="Who is affected">{s.who_is_affected}</Block>}
                    {s.technical_impact?.description && (
                      <Block title="Technical impact">
                        <Badge variant="outline" className="mr-1.5">{s.technical_impact.level}</Badge>
                        {s.technical_impact.description}
                      </Block>
                    )}
                    {s.detailed_explanation && <Block title="Details">{s.detailed_explanation}</Block>}
                    {s.recommended_actions.length > 0 && (
                      <Block title="Recommended actions">
                        <ul className="list-disc space-y-1 pl-5">{s.recommended_actions.map((a) => <li key={a}>{a}</li>)}</ul>
                      </Block>
                    )}
                    {s.related_technologies.length > 0 && (
                      <Block title="Related technologies">
                        <div className="flex flex-wrap gap-1.5">{s.related_technologies.map((t) => <Badge key={t} variant="secondary">{t}</Badge>)}</div>
                      </Block>
                    )}
                    {(s.unsupported_claims_removed.length > 0 || s.actions_removed.length > 0) && (
                      <p className="rounded-md bg-amber-500/10 px-2 py-1.5 text-[11px] text-amber-800 dark:text-amber-200">
                        Fact check: {s.unsupported_claims_removed.length + s.actions_removed.length} statement(s) not supported by the source were removed.
                      </p>
                    )}
                    <Block title="Source references">
                      <ul className="space-y-1">
                        {s.source_references.map((u) => (
                          <li key={u}>
                            <a href={safeUrl(u)} target="_blank" rel="noopener noreferrer" className="break-all text-xs text-primary hover:underline">{u}</a>
                          </li>
                        ))}
                      </ul>
                    </Block>
                  </div>
                )}
              </section>

              {s && s.learning_resources.length > 0 && (
                <Block title="Learn more">
                  <ul className="space-y-1.5">
                    {s.learning_resources.map((r) => (
                      <li key={r.title + (r.url ?? "")} className="flex items-start gap-2 text-sm">
                        <BookOpen className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                        {r.url ? (
                          <a href={safeUrl(r.url)} target="_blank" rel="noopener noreferrer" className="hover:text-primary hover:underline">{r.title}</a>
                        ) : (
                          <span>
                            {r.title} <span className="text-[11px] text-muted-foreground">(AI-suggested topic)</span>
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </Block>
              )}

              {(d.keywords.length > 0 || d.entities.length > 0) && (
                <Block title="Keywords & entities (extracted without AI)">
                  <div className="flex flex-wrap gap-1.5">
                    {d.keywords.map((k) => <Badge key={`k-${k}`} variant="outline"><Tags /> {k}</Badge>)}
                    {d.entities.filter((e) => e.type !== "version").map((e) => (
                      <Badge key={`e-${e.type}-${e.value}`} variant="secondary" title={e.type}>{e.value}</Badge>
                    ))}
                  </div>
                  {d.language && <p className="mt-2 text-[11px] text-muted-foreground">Detected language: {d.language}</p>}
                </Block>
              )}
            </>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}
