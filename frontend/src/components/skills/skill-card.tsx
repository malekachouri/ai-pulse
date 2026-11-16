"use client";

import { Check, Copy, ExternalLink, Package, Plug, Sparkles, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SkillExplanationPanel } from "@/components/skills/skill-explanation";
import { Card, CardContent } from "@/components/ui/card";
import type { Skill, SkillKind } from "@/lib/types";
import { formatDateTime, safeUrl, timeAgo } from "@/lib/utils";

export const KIND: Record<SkillKind, { label: string; plural: string; icon: LucideIcon; hint: string }> = {
  mcp_server: { label: "MCP server", plural: "MCP servers", icon: Plug, hint: "Gives an AI assistant new tools and data through the Model Context Protocol." },
  plugin: { label: "Plugin", plural: "Plugins", icon: Package, hint: "A Claude Code plugin: commands, agents, skills, hooks or MCP servers in one install." },
  skill: { label: "Agent Skill", plural: "Agent Skills", icon: Sparkles, hint: "Instructions and scripts an AI agent loads when a task needs them (a SKILL.md folder)." },
};

/** The technologies the radar tags entries with, as named on the page. */
export const STACK_LABEL: Record<string, string> = {
  postgresql: "PostgreSQL",
  redis: "Redis",
  docker: "Docker",
  kubernetes: "Kubernetes",
  github: "GitHub",
  security: "Security",
  python: "Python",
  typescript: "TypeScript / Next.js",
  ollama: "Ollama / local models",
  observability: "Monitoring",
  testing: "Testing",
};

function CopyButton({ text, label }: { text: string; label: string }) {
  const [done, setDone] = useState(false);
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      aria-label={`Copy: ${label}`}
      className="h-7 shrink-0 px-2"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1500);
        } catch {
          toast.error("Copy failed: select the command and copy it by hand.");
        }
      }}
    >
      {done ? <Check aria-hidden /> : <Copy aria-hidden />}
      <span className="sr-only sm:not-sr-only">{done ? "Copied" : "Copy"}</span>
    </Button>
  );
}

function Link({ href, children }: { href: string | null; children: React.ReactNode }) {
  const url = safeUrl(href);
  if (!url) return null;
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary-tint-fg underline-offset-2 hover:underline">
      {children} <ExternalLink className="size-3" aria-hidden />
    </a>
  );
}

/** When the entry appeared: the listing's own date when it has one, and when AI Pulse first saw it. */
export function seenLine(s: Pick<Skill, "published_at" | "first_seen_at" | "initial" | "kind">): string {
  const parts: string[] = [];
  if (s.published_at) parts.push(`${s.kind === "mcp_server" ? "Version published" : "Published"} ${formatDateTime(s.published_at)}`);
  parts.push(s.initial ? "Listed before AI Pulse started watching this source" : `First seen ${timeAgo(s.first_seen_at)}`);
  return parts.join(" · ");
}

export function SkillCard({ s, llmAvailable = false }: { s: Skill; llmAvailable?: boolean }) {
  const k = KIND[s.kind];
  const id = `skill-${s.id}`;
  return (
    <section aria-labelledby={id}>
      <Card>
        <CardContent className="space-y-3 pt-5">
          <div className="flex flex-wrap items-start gap-x-3 gap-y-1.5">
            <h2 id={id} className="flex min-w-0 items-center gap-1.5 text-base font-semibold">
              <k.icon className="size-4 shrink-0 text-primary" aria-hidden />
              <span className="break-words">{s.title || s.name}</span>
            </h2>
            <Badge variant="outline" title={k.hint}>{k.label}</Badge>
            {s.version && <Badge variant="outline">v{s.version}</Badge>}
            {s.status !== "active" && <Badge className="border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-300">{s.status}</Badge>}
            {s.is_new && <Badge title="First seen by AI Pulse in the last 7 days">New</Badge>}
          </div>
          <p className="text-xs text-muted-foreground">
            {s.title && s.title !== s.name && <><span className="font-mono">{s.name}</span> · </>}
            {s.publisher && <>by {s.publisher} · </>}
            {s.category && <>{s.kind === "skill" ? "in plugin" : "category"} {s.category} · </>}
            from {s.source.name}
          </p>
          {s.description && <p className="line-clamp-4 whitespace-pre-line text-sm">{s.description}</p>}
          {s.stack_tags.length > 0 && (
            <p className="flex flex-wrap items-center gap-1.5 text-xs">
              <span className="font-medium">Technologies:</span>
              {s.stack_tags.map((t) => <Badge key={t} variant="outline">{STACK_LABEL[t] ?? t}</Badge>)}
            </p>
          )}
          {s.install.length > 0 && (
            <details className="rounded-lg border bg-muted/30 px-3 py-2 text-sm">
              <summary className="cursor-pointer font-medium">How to install ({s.install.length} option{s.install.length === 1 ? "" : "s"})</summary>
              <ol className="mt-2 space-y-3">
                {s.install.map((step, i) => (
                  <li key={i} className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">{step.label}</p>
                    {step.command ? (
                      <div className="flex items-start gap-2">
                        <pre className="min-w-0 flex-1 overflow-x-auto rounded-md bg-background px-2 py-1.5 font-mono text-xs"><code>{step.command}</code></pre>
                        <CopyButton text={step.command} label={step.label} />
                      </div>
                    ) : null}
                    {step.notes.length > 0 && (
                      <ul className="list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">
                        {step.notes.map((n) => <li key={n}>{n}</li>)}
                      </ul>
                    )}
                  </li>
                ))}
              </ol>
              <p className="mt-2 text-xs text-muted-foreground">Built from the official listing. Read what a server or plugin does before installing it: AI Pulse does not review third-party code.</p>
            </details>
          )}
          <SkillExplanationPanel s={s} llmAvailable={llmAvailable} />
          <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
            <Link href={s.listing_url}>Official listing</Link>
            <Link href={s.homepage_url}>Website</Link>
            <Link href={s.repository_url}>Source code</Link>
          </p>
          <p className="text-xs text-muted-foreground">{seenLine(s)}</p>
        </CardContent>
      </Card>
    </section>
  );
}
