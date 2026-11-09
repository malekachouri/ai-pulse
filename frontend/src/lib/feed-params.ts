/** Pure helpers that map URL search params <-> feed filter state <-> API query. */
import type { ArticleFilters, ItemType, Severity, SortOrder } from "@/lib/types";

export type DateRange = "any" | "24h" | "7d" | "30d" | "custom";

export interface FeedState {
  q: string;
  types: ItemType[];
  categories: string[];
  sources: string[];
  severities: Severity[];
  minImportance: number | null;
  range: DateRange;
  from: string; // yyyy-mm-dd (custom range)
  to: string;
  sort: SortOrder;
  page: number;
}

const SEVERITIES: Severity[] = ["critical", "high", "medium", "low", "info"];
const SORTS: SortOrder[] = ["latest", "importance", "relevance"];
const RANGES: DateRange[] = ["any", "24h", "7d", "30d", "custom"];
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export const PAGE_SIZE = 20;

type ParamsLike = { get(name: string): string | null; getAll(name: string): string[] };

export function parseFeedState(params: ParamsLike, allowedTypes: ItemType[]): FeedState {
  const page = Number.parseInt(params.get("page") ?? "1", 10);
  const imp = params.get("min_importance");
  const minImportance = imp !== null && /^\d+$/.test(imp) ? Math.min(100, Number(imp)) : null;
  const range = params.get("range") as DateRange | null;
  const sort = params.get("sort") as SortOrder | null;
  const from = params.get("from") ?? "";
  const to = params.get("to") ?? "";
  return {
    q: (params.get("q") ?? "").slice(0, 300),
    types: params.getAll("type").filter((t): t is ItemType => allowedTypes.includes(t as ItemType)),
    categories: params.getAll("category").filter((c) => /^[a-z0-9-]{1,64}$/.test(c)),
    sources: params.getAll("source").filter((s) => /^[a-z0-9-]{1,100}$/.test(s)),
    severities: params.getAll("severity").filter((s): s is Severity => SEVERITIES.includes(s as Severity)),
    minImportance,
    range: range && RANGES.includes(range) ? range : "any",
    from: DATE_RE.test(from) ? from : "",
    to: DATE_RE.test(to) ? to : "",
    sort: sort && SORTS.includes(sort) ? sort : "latest",
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

export function serializeFeedState(s: FeedState): string {
  const sp = new URLSearchParams();
  if (s.q) sp.set("q", s.q);
  s.types.forEach((t) => sp.append("type", t));
  s.categories.forEach((c) => sp.append("category", c));
  s.sources.forEach((c) => sp.append("source", c));
  s.severities.forEach((c) => sp.append("severity", c));
  if (s.minImportance !== null) sp.set("min_importance", String(s.minImportance));
  if (s.range !== "any") sp.set("range", s.range);
  if (s.range === "custom") {
    if (s.from) sp.set("from", s.from);
    if (s.to) sp.set("to", s.to);
  }
  if (s.sort !== "latest") sp.set("sort", s.sort);
  if (s.page > 1) sp.set("page", String(s.page));
  return sp.toString();
}

const HOURS: Record<"24h" | "7d" | "30d", number> = { "24h": 24, "7d": 168, "30d": 720 };

/**
 * Build the API query. `now` is rounded to the minute by the caller so the query key stays
 * stable between renders. Relevance sort without a search term falls back to latest (as the API does).
 */
export function toApiFilters(s: FeedState, baseTypes: ItemType[], now: number): ArticleFilters {
  let date_from: string | undefined;
  let date_to: string | undefined;
  if (s.range === "custom") {
    if (s.from) date_from = new Date(`${s.from}T00:00:00`).toISOString();
    if (s.to) date_to = new Date(`${s.to}T23:59:59.999`).toISOString();
  } else if (s.range !== "any") {
    date_from = new Date(now - HOURS[s.range] * 3_600_000).toISOString();
  }
  return {
    q: s.q || undefined,
    item_type: s.types.length ? s.types : baseTypes.length ? baseTypes : undefined,
    category: s.categories.length ? s.categories : undefined,
    source: s.sources.length ? s.sources : undefined,
    severity: s.severities.length ? s.severities : undefined,
    min_importance: s.minImportance ?? undefined,
    date_from,
    date_to,
    sort: s.sort === "relevance" && !s.q ? "latest" : s.sort,
    page: s.page,
    page_size: PAGE_SIZE,
  };
}

export function activeFilterCount(s: FeedState): number {
  return (
    s.types.length + s.categories.length + s.sources.length + s.severities.length +
    (s.minImportance !== null ? 1 : 0) + (s.range !== "any" ? 1 : 0)
  );
}
