"use client";

import { Loader2, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { useExplainSkill, useSkillExplanation } from "@/lib/queries";
import type { Skill, SkillExplanation } from "@/lib/types";
import { formatDateTime, safeUrl } from "@/lib/utils";

const SECTIONS: { key: keyof NonNullable<SkillExplanation["sections"]>; label: string }[] = [
  { key: "what_it_does", label: "What it does" },
  { key: "use_cases", label: "What it is good for" },
  { key: "how_to_try", label: "How to try it" },
  { key: "cautions", label: "Before you use it" },
];

function Cite({ n, d }: { n: number; d: SkillExplanation }) {
  const src = d.sources.find((s) => s.n === n);
  const url = safeUrl(src?.url);
  const label = `Source ${n}: ${src?.title ?? "unknown"}`;
  return url ? (
    <a href={url} target="_blank" rel="noopener noreferrer" aria-label={label} title={label} className="text-primary-tint-fg underline underline-offset-2">[{n}]</a>
  ) : (
    <span aria-label={label} title={label}>[{n}]</span>
  );
}

/** The stored explanation: four sections, each AI-written and cited, or "insufficient information". */
export function ExplanationView({ d }: { d: SkillExplanation }) {
  if (!d.sections) return null;
  return (
    <div className="space-y-2">
      <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge className="border-brand-violet/40 bg-brand-violet/10 text-foreground"><Sparkles className="size-3" aria-hidden /> AI-generated</Badge>
        {d.provider && <span>{d.provider} · {d.model}</span>}
        {d.generated_at && <span>· {formatDateTime(d.generated_at)}</span>}
        {d.listing_version && <span>· for version {d.listing_version}</span>}
      </p>
      <dl className="space-y-2 text-sm">
        {SECTIONS.map(({ key, label }) => {
          const part = d.sections?.[key];
          if (!part) return null;
          return (
            <div key={key}>
              <dt className="text-xs font-semibold">{label}</dt>
              <dd className={part.insufficient ? "text-muted-foreground italic" : undefined}>
                {part.insufficient ? "Insufficient information in the sources." : part.text}{" "}
                {part.citations.map((n) => <Cite key={n} n={n} d={d} />)}
              </dd>
            </div>
          );
        })}
      </dl>
      <p className="text-xs text-muted-foreground">
        Written only from: {d.sources.map((s) => `[${s.n}] ${s.title}`).join(" · ")}. Sentences with numbers or versions the sources do not contain are removed
        {d.unsupported_claims_removed.length > 0 && ` (removed here: ${d.unsupported_claims_removed.join(", ")})`}. Check the listing before installing.
      </p>
    </div>
  );
}

export function SkillExplanationPanel({ s, llmAvailable }: { s: Skill; llmAvailable: boolean }) {
  if (!llmAvailable && !s.explained_at) return null; // nothing to show and nothing to generate
  return <Panel s={s} llmAvailable={llmAvailable} />;
}

function Panel({ s, llmAvailable }: { s: Skill; llmAvailable: boolean }) {
  const { status } = useAuth();
  const [open, setOpen] = useState(false);
  const stored = useSkillExplanation(s.id, open && !!s.explained_at);
  const gen = useExplainSkill(s.id);
  const d = gen.data?.status && gen.data.status !== "failed" ? gen.data : stored.data;
  const has = d && d.status !== "none" && d.sections;

  return (
    <div className="rounded-lg border border-brand-violet/30 bg-brand-violet/5 px-3 py-2">
      {!open ? (
        <Button variant="ghost" size="sm" className="h-7 px-2" onClick={() => setOpen(true)} aria-expanded={false}>
          <Sparkles aria-hidden /> {s.explained_at ? "Show the AI explanation" : "What is it good for? (AI)"}
        </Button>
      ) : (
        <div className="space-y-2" aria-live="polite">
          {stored.isLoading ? (
            <p className="text-xs text-muted-foreground"><Loader2 className="inline size-3 animate-spin" aria-hidden /> Loading…</p>
          ) : has ? (
            <ExplanationView d={d} />
          ) : null}
          {gen.isPending ? (
            <p className="text-xs text-muted-foreground">
              <Loader2 className="inline size-3 animate-spin" aria-hidden /> The AI model is reading the listing and the README. With a local model this can take a few minutes.
            </p>
          ) : !llmAvailable ? (
            <p className="text-xs text-muted-foreground">No AI model is configured, so it cannot be regenerated.</p>
          ) : status !== "authenticated" ? (
            <p className="text-xs text-muted-foreground"><Link href="/login" className="underline">Sign in</Link> to ask the AI model.</p>
          ) : (
            <Button variant="outline" size="sm" onClick={() => gen.mutate()}>
              <Sparkles aria-hidden /> {has ? "Regenerate with AI" : "Explain with AI"}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
