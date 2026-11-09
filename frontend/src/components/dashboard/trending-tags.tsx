import { Hash } from "lucide-react";
import Link from "next/link";

import type { CountByKey } from "@/lib/types";

export function TrendingTags({ tags }: { tags: CountByKey[] }) {
  if (!tags.length)
    return <p className="py-6 text-center text-sm text-muted-foreground">No tags collected in the last 7 days.</p>;
  const max = Math.max(...tags.map((t) => t.count));
  return (
    <ul className="space-y-2">
      {tags.slice(0, 8).map((t, i) => (
        <li key={t.key} className="flex items-center gap-3 text-sm">
          <span className="tabular w-4 text-xs text-muted-foreground">{i + 1}</span>
          <Link
            href={`/search?q=${encodeURIComponent(t.key)}&sort=relevance`}
            className="flex min-w-0 flex-1 items-center gap-1 hover:text-primary"
          >
            <Hash className="size-3.5 shrink-0 text-muted-foreground" />
            <span className="truncate">{t.key}</span>
          </Link>
          <span className="relative h-1.5 w-20 overflow-hidden rounded-full bg-muted" aria-hidden>
            <span
              className="absolute inset-y-0 left-0 rounded-full bg-[var(--chart-series)]"
              style={{ width: `${(t.count / max) * 100}%` }}
            />
          </span>
          <span className="tabular w-6 text-right text-xs text-muted-foreground">{t.count}</span>
        </li>
      ))}
    </ul>
  );
}
