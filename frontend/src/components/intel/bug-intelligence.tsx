"use client";

import { Loader2, Microscope, Sparkles } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";
import { useBugIntelligence, useGenerateBugIntelligence } from "@/lib/queries";
import type { BugIntelligence as Intel, BugSection, ItemType } from "@/lib/types";
import { formatDateTime, safeUrl } from "@/lib/utils";

export const BUG_INTEL_TYPES: ItemType[] = ["bug", "vulnerability", "github_issue"];

const SECTIONS: { key: keyof Intel["sections"]; label: string }[] = [
  { key: "cause", label: "Why it occurs" },
  { key: "impact", label: "Impact" },
  { key: "affected_versions", label: "Affected versions" },
  { key: "fixes", label: "Available fixes" },
];

const KIND_LABEL: Record<string, string> = {
  issue: "Issue",
  advisory: "Advisory",
  cve_record: "CVE record",
  bug_record: "Issue record",
  release_notes: "Release notes",
  fix: "Fix",
};

function Cites({ ns, intel }: { ns: number[]; intel: Intel }) {
  return (
    <>
      {ns.map((n) => {
        const src = intel.sources.find((s) => s.n === n);
        if (!src) return null;
        return (
          <a
            key={n}
            href={safeUrl(src.url)}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-0.5 align-super text-[10px] font-semibold text-primary underline underline-offset-2"
            aria-label={`Source ${n}: ${src.title}`}
          >
            [{n}]
          </a>
        );
      })}
    </>
  );
}

function Section({ label, s, intel }: { label: string; s: BugSection; intel: Intel }) {
  return (
    <div className="space-y-1">
      <dt className="text-xs font-semibold">{label}</dt>
      <dd className="space-y-1 text-xs leading-relaxed">
        {s.status === "insufficient" ? (
          <p className="italic text-muted-foreground">Insufficient information in the collected sources.</p>
        ) : (
          <>
            {s.facts.length > 0 && (
              <ul className="list-disc space-y-0.5 pl-4">
                {s.facts.map((f, i) => (
                  <li key={i}>
                    {f.text}
                    <Cites ns={[f.citation]} intel={intel} />
                  </li>
                ))}
              </ul>
            )}
            {s.text && (
              <p>
                {s.text_is_ai && (
                  <Sparkles className="mr-1 inline size-3 text-brand-violet" aria-label="AI-generated" />
                )}
                {s.text}
                <Cites ns={s.citations} intel={intel} />
              </p>
            )}
          </>
        )}
      </dd>
    </div>
  );
}

/** What the panel says about the AI layer: generated, nothing usable, possible, or unavailable. */
export function footer(d: Intel, signedIn: boolean, pending = false): string {
  if (pending) return "The AI model is reading the sources. With a local model this can take a few minutes.";
  const removed = d.unsupported_claims_removed.length
    ? ` ${d.unsupported_claims_removed.length} unsupported claim(s) removed.`
    : "";
  if (d.status === "ready") {
    const by = `${d.provider} / ${d.model}, ${formatDateTime(d.generated_at)}`;
    return Object.values(d.sections).some((s) => s.text_is_ai)
      ? `Explanation by ${by}, checked against the cited sources.${removed}`
      : `The AI model (${by}) added nothing that the cited sources support, so only the facts are shown.${removed}`;
  }
  if (!d.llm_available) return "Facts only: AI explanations need an LLM provider.";
  return signedIn ? "Facts only. An AI explanation can be generated from these sources." : "Facts only. Sign in to generate an AI explanation.";
}

/** The cited findings (pure: rendered from the API response). */
export function BugIntelligenceFindings({ d }: { d: Intel }) {
  return (
    <>
    <p className="mt-0.5 text-[11px] text-muted-foreground">
      {d.subject.id} · only from the official sources listed below; nothing is inferred.
    </p>
    <dl className="mt-3 space-y-3">
      {SECTIONS.map(({ key, label }) => (
        <Section key={key} label={label} s={d.sections[key]} intel={d} />
      ))}
    </dl>
    <h4 className="mt-4 text-xs font-semibold">Sources</h4>
    <ol className="mt-1 space-y-0.5 text-xs">
      {d.sources.map((s) => (
        <li key={s.n}>
          [{s.n}] <span className="text-muted-foreground">{KIND_LABEL[s.kind] ?? s.kind}:</span>{" "}
          <a href={safeUrl(s.url)} target="_blank" rel="noopener noreferrer" className="text-primary underline underline-offset-2">
            {s.title}
          </a>
        </li>
      ))}
    </ol>
    </>
  );
}

/** Bug Intelligence: cause, impact, affected versions and fixes, each cited to the collected official sources. */
export function BugIntelligencePanel({ articleId }: { articleId: string }) {
  const q = useBugIntelligence(articleId);
  const gen = useGenerateBugIntelligence(articleId);
  const { status } = useAuth();
  const d = q.data;
  return (
    <section className="rounded-xl border bg-card p-4" aria-labelledby="bug-intel-title">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="bug-intel-title" className="flex items-center gap-1.5 text-sm font-semibold">
          <Microscope className="size-4 text-primary" aria-hidden /> Bug intelligence
        </h3>
        {d?.ai_generated && (
          <Badge variant="secondary" className="gap-1">
            <Sparkles className="size-3" aria-hidden /> AI-generated
          </Badge>
        )}
      </div>
      {q.isLoading ? (
        <Skeleton className="mt-3 h-32" />
      ) : q.isError || !d ? (
        <p className="mt-2 text-xs text-muted-foreground">Bug intelligence is not available for this item.</p>
      ) : (
        <>
          <BugIntelligenceFindings d={d} />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t pt-3 text-[11px] text-muted-foreground">
            <span>
              {footer(d, status === "authenticated", gen.isPending)}
            </span>
            {d.llm_available && status === "authenticated" && (
              <Button variant="outline" size="sm" onClick={() => gen.mutate()} disabled={gen.isPending}>
                {gen.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />}{" "}
                {d.status === "ready" ? "Regenerate with AI" : "Explain with AI"}
              </Button>
            )}
          </div>
        </>
      )}
    </section>
  );
}

/** A small row action (bug and CVE tables) that opens the explanation in a side sheet. */
export function BugIntelligenceButton({ articleId, label }: { articleId: string | null; label: string }) {
  const [open, setOpen] = useState(false);
  if (!articleId) return null;
  return (
    <>
      <Button variant="ghost" size="sm" className="h-7 gap-1 px-2 text-xs" onClick={() => setOpen(true)} aria-label={`Bug intelligence: ${label}`}>
        <Microscope className="size-3.5" aria-hidden /> Explain
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="right" title={`Bug intelligence: ${label}`} className="w-[min(100vw,560px)] max-w-none overflow-y-auto bg-background p-0">
          <div className="space-y-4 p-5 pr-10">
            <h2 className="text-base font-semibold leading-snug">{label}</h2>
            {open && <BugIntelligencePanel articleId={articleId} />}
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
