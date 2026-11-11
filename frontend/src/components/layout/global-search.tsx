"use client";

import { Search } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

/** Searches across every collected item type; "/" focuses it from anywhere. */
export function GlobalSearch() {
  const router = useRouter();
  const params = useSearchParams();
  const [value, setValue] = useState(params.get("q") ?? "");
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(t?.tagName ?? "") && !t?.isContentEditable) {
        e.preventDefault();
        ref.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <form
      role="search"
      aria-label="Site search"
      className="relative w-full max-w-md"
      onSubmit={(e) => {
        e.preventDefault();
        const q = value.trim();
        router.push(q ? `/search?q=${encodeURIComponent(q)}&sort=relevance` : "/search");
      }}
    >
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
      <input
        ref={ref}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        type="search"
        maxLength={300}
        placeholder="Search…"
        aria-label="Search all intelligence"
        className="h-9 w-full rounded-lg border border-input bg-muted/50 pl-9 pr-10 text-sm outline-none transition placeholder:text-muted-foreground focus:border-ring focus:bg-card focus:ring-[3px] focus:ring-ring/30"
      />
      <kbd className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 rounded border bg-card px-1.5 text-[10px] text-muted-foreground sm:block">
        /
      </kbd>
    </form>
  );
}
