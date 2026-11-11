"use client";

import { GitCompareArrows } from "lucide-react";

import type { ReleaseChanges as Changes } from "@/lib/types";
import { safeUrl } from "@/lib/utils";

const NOT_DOCUMENTED = "not documented";

/** [1] = this release, [2] = the previous one: every fact below points at the source that states it. */
function Cite({ n, href }: { n: 1 | 2; href: string }) {
  return (
    <a
      href={safeUrl(href)}
      target="_blank"
      rel="noopener noreferrer"
      className="ml-0.5 align-super text-[10px] font-semibold text-primary underline underline-offset-2"
      aria-label={n === 1 ? "Source: this release" : "Source: previous release"}
    >
      [{n}]
    </a>
  );
}

function Value({ v }: { v: string | number }) {
  return v === NOT_DOCUMENTED ? <span className="italic text-muted-foreground">not documented</span> : <span className="tabular">{v}</span>;
}

const KIND_LABEL: Record<string, string> = { breaking: "Breaking", security: "Security", features: "Features", fixes: "Fixes", other: "Other" };

export function ReleaseChanges({ c }: { c: Changes }) {
  const cur = c.citations.current;
  const prev = c.citations.previous;
  return (
    <section className="rounded-xl border bg-card p-4" aria-labelledby="release-changes-title">
      <h3 id="release-changes-title" className="flex items-center gap-1.5 text-sm font-semibold">
        <GitCompareArrows className="size-4 text-primary" /> What changed since {c.version_change.from}
      </h3>
      <p className="mt-0.5 text-[11px] text-muted-foreground">{c.method}</p>

      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs">
        <dt className="text-muted-foreground">Version</dt>
        <dd>
          <Value v={c.version_change.from} />
          <Cite n={2} href={prev} /> → <Value v={c.version_change.to} />
          <Cite n={1} href={cur} />
          {c.version_change.bump && c.version_change.bump !== "none" && <span className="ml-1.5 text-muted-foreground">({c.version_change.bump})</span>}
        </dd>
        <dt className="text-muted-foreground">License</dt>
        <dd>
          <Value v={c.license.previous.value} />
          {c.license.previous.value !== NOT_DOCUMENTED && <Cite n={2} href={prev} />} → <Value v={c.license.current.value} />
          {c.license.current.value !== NOT_DOCUMENTED && <Cite n={1} href={cur} />}
          <span className="ml-1.5 text-muted-foreground">({c.license.status})</span>
        </dd>
      </dl>

      <h4 className="mt-4 text-xs font-semibold">Benchmarks quoted by the sources</h4>
      {c.benchmarks.length === 0 ? (
        <p className="mt-1 text-xs italic text-muted-foreground">Not documented in either release.</p>
      ) : (
        <div className="mt-1 overflow-x-auto rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring" tabIndex={0} role="region" aria-label="Benchmark comparison">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-1 font-medium">Benchmark</th>
                <th className="py-1 text-right font-medium">Previous</th>
                <th className="py-1 text-right font-medium">This release</th>
                <th className="py-1 text-right font-medium">Change</th>
              </tr>
            </thead>
            <tbody>
              {c.benchmarks.map((b) => (
                <tr key={b.name} className="border-b last:border-0">
                  <td className="py-1">{b.name}</td>
                  <td className="py-1 text-right" title={b.quotes.previous ?? undefined}>
                    <Value v={b.previous} />
                    {b.quotes.previous && <Cite n={2} href={prev} />}
                  </td>
                  <td className="py-1 text-right" title={b.quotes.current ?? undefined}>
                    <Value v={b.current} />
                    {b.quotes.current && <Cite n={1} href={cur} />}
                  </td>
                  <td className="tabular py-1 text-right">{b.delta == null ? "—" : `${b.delta > 0 ? "+" : ""}${b.delta}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h4 className="mt-4 text-xs font-semibold">
        Changelog of this release <Cite n={1} href={cur} />
      </h4>
      {c.changelog.sections.length === 0 ? (
        <p className="mt-1 text-xs italic text-muted-foreground">Not documented in the release notes.</p>
      ) : (
        <div className="mt-1 space-y-2">
          {c.changelog.sections.map((s, i) => (
            <div key={`${s.heading}-${i}`}>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                {KIND_LABEL[s.kind] ?? s.kind}: {s.heading}
              </p>
              <ul className="mt-0.5 list-disc space-y-0.5 pl-4 text-xs">
                {s.items.map((it, j) => (
                  <li key={j}>{it}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      <p className="mt-3 text-[11px] text-muted-foreground">
        [1] <a className="underline underline-offset-2" href={safeUrl(cur)} target="_blank" rel="noopener noreferrer">{c.current.title}</a> · [2]{" "}
        <a className="underline underline-offset-2" href={safeUrl(prev)} target="_blank" rel="noopener noreferrer">{c.previous.title}</a>
      </p>
    </section>
  );
}
