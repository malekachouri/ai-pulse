import { describe, expect, it } from "vitest";

import { activeFilterCount, parseFeedState, serializeFeedState, toApiFilters } from "@/lib/feed-params";
import type { ItemType } from "@/lib/types";

const ALL: ItemType[] = ["bug", "incident"];
const parse = (qs: string, allowed = ALL) => parseFeedState(new URLSearchParams(qs), allowed);

describe("parseFeedState", () => {
  it("returns defaults for an empty query", () => {
    const s = parse("");
    expect(s).toMatchObject({ q: "", sort: "latest", page: 1, range: "any", minImportance: null });
    expect(activeFilterCount(s)).toBe(0);
  });

  it("drops invalid and disallowed values", () => {
    const s = parse(
      "type=bug&type=vulnerability&severity=critical&severity=apocalyptic&sort=random&page=-3&min_importance=abc&range=1y&from=yesterday&category=Bad Slug",
    );
    expect(s.types).toEqual(["bug"]);
    expect(s.severities).toEqual(["critical"]);
    expect(s.sort).toBe("latest");
    expect(s.page).toBe(1);
    expect(s.minImportance).toBeNull();
    expect(s.range).toBe("any");
    expect(s.from).toBe("");
    expect(s.categories).toEqual([]);
  });

  it("clamps importance and truncates long queries", () => {
    const s = parse(`min_importance=500&q=${"x".repeat(400)}`);
    expect(s.minImportance).toBe(100);
    expect(s.q).toHaveLength(300);
  });
});

describe("serializeFeedState", () => {
  it("round-trips through the URL", () => {
    const qs = "q=rag&type=bug&category=rag&source=nvd&severity=high&min_importance=50&range=custom&from=2026-01-01&to=2026-01-31&sort=importance&page=3";
    const s = parse(qs);
    expect(parse(serializeFeedState(s))).toEqual(s);
  });

  it("omits defaults and custom dates when range is not custom", () => {
    expect(serializeFeedState({ ...parse(""), from: "2026-01-01" })).toBe("");
  });
});

describe("toApiFilters", () => {
  const now = Date.parse("2026-11-09T12:00:00Z");

  it("uses the page's base types when no type filter is chosen", () => {
    expect(toApiFilters(parse(""), ALL, now).item_type).toEqual(ALL);
    expect(toApiFilters(parse("type=incident"), ALL, now).item_type).toEqual(["incident"]);
    expect(toApiFilters(parse("", ALL), [], now).item_type).toBeUndefined();
  });

  it("computes relative and custom date ranges", () => {
    expect(toApiFilters(parse("range=24h"), ALL, now).date_from).toBe("2026-11-08T12:00:00.000Z");
    const custom = toApiFilters(parse("range=custom&from=2026-01-01&to=2026-01-02"), ALL, now);
    expect(custom.date_from).toBeDefined();
    expect(Date.parse(custom.date_to!)).toBeGreaterThan(Date.parse(custom.date_from!));
  });

  it("falls back from relevance to latest without a search term", () => {
    expect(toApiFilters(parse("sort=relevance"), ALL, now).sort).toBe("latest");
    expect(toApiFilters(parse("sort=relevance&q=k8s"), ALL, now).sort).toBe("relevance");
  });
});
