"use client";

import { Loader2, MessageSquareText, SearchX, Sparkles } from "lucide-react";
import { Fragment, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ITEM_TYPE_LABEL } from "@/lib/labels";
import { useAsk, useSearchCapabilities } from "@/lib/queries";
import type { AskCitation } from "@/lib/types";
import { safeUrl, timeAgo } from "@/lib/utils";

const EXAMPLES = [
  "What are the latest important developments in RAG?",
  "Which Kubernetes vulnerabilities were recently disclosed?",
  "What are the most important AI model releases this week?",
  "What new bugs are affecting popular AI frameworks?",
];

/** Renders "[n]" markers as links to the cited source. Text is never parsed as HTML. */
function WithCitations({ text, sources }: { text: string; sources: AskCitation[] }) {
  const parts = text.split(/(\[\d{1,2}\])/g);
  return (
    <p className="text-sm leading-relaxed">
      {parts.map((p, i) => {
        const m = p.match(/^\[(\d{1,2})\]$/);
        const src = m ? sources.find((s) => s.n === Number(m[1])) : undefined;
        return src ? (
          <a key={i} href={safeUrl(src.url)} target="_blank" rel="noopener noreferrer" title={src.title}
             className="mx-0.5 rounded bg-primary/15 px-1 text-[11px] font-semibold text-primary-tint-fg hover:bg-primary/25">
            {src.n}
          </a>
        ) : (
          <Fragment key={i}>{p}</Fragment>
        );
      })}
    </p>
  );
}

function SourceList({ sources }: { sources: AskCitation[] }) {
  return (
    <ol className="space-y-2">
      {sources.map((s) => (
        <li key={s.article_id} className="flex gap-2 text-sm">
          <span className="tabular mt-0.5 w-5 shrink-0 text-xs font-semibold text-muted-foreground">[{s.n}]</span>
          <div className="min-w-0">
            <a href={safeUrl(s.url)} target="_blank" rel="noopener noreferrer" className="font-medium leading-snug hover:text-primary">{s.title}</a>
            <p className="text-[11px] text-muted-foreground">
              {s.source} · {ITEM_TYPE_LABEL[s.item_type] ?? s.item_type} · {timeAgo(s.published_at)}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function AskPanel() {
  const [q, setQ] = useState("");
  const ask = useAsk();
  const caps = useSearchCapabilities();
  const r = ask.data;
  const submit = (question: string) => question.trim().length >= 5 && ask.mutate(question.trim());

  return (
    <Card className="mb-6 overflow-hidden">
      <div className="pointer-events-none absolute" />
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageSquareText className="size-4 text-primary" /> Ask AI Pulse
        </CardTitle>
        <Badge variant={caps.data?.ask_mode === "generative" ? "violet" : "secondary"}>
          {caps.data?.ask_mode === "generative" ? "AI answers with citations" : "Sources only (no LLM configured)"}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); submit(q); }}>
          <Input value={q} onChange={(e) => setQ(e.target.value)} maxLength={500} placeholder="Ask about AI, security, bugs or cloud…" aria-label="Question" />
          <Button type="submit" variant="brand" disabled={ask.isPending || q.trim().length < 5}>
            {ask.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />} Ask
          </Button>
        </form>
        {!r && !ask.isPending && (
          <div className="flex flex-wrap gap-1.5">
            {EXAMPLES.map((e) => (
              <button key={e} type="button" onClick={() => { setQ(e); submit(e); }} className="rounded-full border px-2.5 py-1 text-xs text-muted-foreground hover:bg-accent">
                {e}
              </button>
            ))}
          </div>
        )}
        {r && (
          <div className="space-y-4 border-t pt-4" aria-live="polite">
            {r.insufficient ? (
              <div className="flex items-start gap-2 rounded-lg bg-muted p-3 text-sm">
                <SearchX className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                <div>
                  <p className="font-medium">Not enough information to answer</p>
                  <p className="mt-0.5 text-muted-foreground">{r.reason}</p>
                </div>
              </div>
            ) : r.answer ? (
              <div className="rounded-lg border border-brand-violet/25 bg-brand-violet/[0.05] p-3">
                <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-violet-700 dark:text-violet-300">
                  <Sparkles className="size-3.5" /> AI-generated answer
                  {r.generated_by && <span className="font-normal normal-case tracking-normal text-muted-foreground">· {r.generated_by.provider}/{r.generated_by.model} · confidence {r.confidence}</span>}
                </p>
                <WithCitations text={r.answer} sources={r.sources} />
                {r.unsupported_claims_removed.length > 0 && (
                  <p className="mt-2 text-[11px] text-amber-700 dark:text-amber-300">
                    {r.unsupported_claims_removed.length} unsupported claim(s) were removed from the answer.
                  </p>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">{r.reason}</p>
            )}
            {r.sources.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {r.answer ? "Sources" : "Most relevant collected items"}
                  <span className="ml-2 font-normal normal-case tracking-normal">
                    retrieval: {r.retrieval.mode}
                    {r.retrieval.item_types.length > 0 && ` · ${r.retrieval.item_types.join(", ")}`}
                    {r.retrieval.date_from && ` · since ${r.retrieval.date_from.slice(0, 10)}`}
                  </span>
                </p>
                <SourceList sources={r.answer ? r.citations : r.sources} />
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
