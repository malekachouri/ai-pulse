import { clsx, type ClassValue } from "clsx";
import { format, formatDistanceToNowStrict, isValid, parseISO } from "date-fns";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

function toDate(value: string | Date | null | undefined): Date | null {
  if (!value) return null;
  const d = typeof value === "string" ? parseISO(value) : value;
  return isValid(d) ? d : null;
}

export function timeAgo(value: string | null | undefined): string {
  const d = toDate(value);
  return d ? `${formatDistanceToNowStrict(d)} ago` : "Unknown date";
}

export function formatDateTime(value: string | null | undefined): string {
  const d = toDate(value);
  return d ? format(d, "d MMM yyyy, HH:mm") : "Unknown";
}

export function formatDay(value: string | null | undefined): string {
  const d = toDate(value);
  return d ? format(d, "d MMM") : "";
}

const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });
export function formatCount(n: number): string {
  return n >= 10_000 ? compact.format(n) : n.toLocaleString("en");
}

export function titleCase(slug: string): string {
  return slug.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Only allow http(s) links from API data to be rendered as hrefs. */
export function safeUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:" ? u.toString() : undefined;
  } catch {
    return undefined;
  }
}
