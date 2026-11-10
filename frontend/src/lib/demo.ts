/**
 * DEMO MODE (NEXT_PUBLIC_DEMO_MODE=true) — a UI preview that needs no backend.
 *
 * Every record here is FICTIONAL and visibly labelled: titles start with "[DEMO]", sources are named
 * "Demo source", and links point to example.com. A permanent banner is shown in the app shell.
 * Never enable this in production; real data comes only from the API.
 */
import type {
  Article,
  Bookmark,
  Briefing,
  BriefingListItem,
  Category,
  AIModel,
  DashboardSummary,
  GitHubRepository,
  ItemType,
  Notification,
  Page,
  Preferences,
  RadarIncident,
  Severity,
  SourceBrief,
  SourceStatus,
  User,
} from "@/lib/types";

export function isDemoMode(): boolean {
  return process.env.NEXT_PUBLIC_DEMO_MODE === "true";
}

const CATS: Category[] = [
  ["ai-models", "AI Models"], ["ai-research", "AI Research"], ["ai-tools", "AI Tools"], ["rag", "RAG"],
  ["llmops", "LLMOps"], ["mlops", "MLOps"], ["ai-agents", "AI Agents"],
  ["software-engineering", "Software Engineering"], ["bugs", "Bugs"],
  ["infrastructure-failures", "Infrastructure Failures"], ["cybersecurity", "Cybersecurity"],
  ["devops", "DevOps"], ["cloud", "Cloud"], ["kubernetes", "Kubernetes"], ["docker", "Docker"],
].map(([slug, name], i) => ({ id: i + 1, slug: slug!, name: name! }));

const SOURCES: SourceBrief[] = [
  { id: "demo-src-1", slug: "demo-vendor-blog", name: "Demo source: vendor blog", source_type: "rss", is_official: true, reliability: 0.9 },
  { id: "demo-src-2", slug: "demo-advisories", name: "Demo source: security advisories", source_type: "api", is_official: true, reliability: 0.95 },
  { id: "demo-src-3", slug: "demo-code-host", name: "Demo source: code host", source_type: "github", is_official: true, reliability: 0.8 },
  { id: "demo-src-4", slug: "demo-status-page", name: "Demo source: status page", source_type: "status_page", is_official: true, reliability: 0.9 },
];

type Seed = [ItemType, string, string, string[], number, Severity | null, number, number, string[]];
// [type, title, description, category slugs, hoursAgo, severity, importance, sourceIndex, tags]
const SEEDS: Seed[] = [
  ["model_release", "Example Labs releases Nimbus-7B open-weights model", "A fictional 7B parameter model with a 128k context window, released under a permissive licence.", ["ai-models"], 3, null, 82, 0, ["llm", "open-weights"]],
  ["news", "Fictional Corp announces agent framework preview", "An imaginary company previews a framework for multi-step tool-using agents.", ["ai-agents", "ai-tools"], 5, null, 64, 0, ["agents", "tool-use"]],
  ["vulnerability", "CVE-0000-00001 in example-http library", "Fictional remote code execution flaw in an imaginary HTTP parser.", ["cybersecurity"], 6, "critical", 95, 1, ["rce", "http"]],
  ["incident", "Demo Cloud: elevated API error rates in region demo-east-1", "Fictional provider reports increased 5xx errors for its object storage API.", ["cloud", "infrastructure-failures"], 2, "high", 77, 3, ["outage", "storage"]],
  ["research", "Sparse retrieval heads improve long-context RAG (demo paper)", "A made-up paper studying retrieval-specialised attention heads.", ["ai-research", "rag"], 9, null, 70, 0, ["rag", "long-context"]],
  ["tool", "vectorlite 2.0 adds hybrid search (fictional)", "An imaginary embedded vector store ships BM25 + vector hybrid ranking.", ["ai-tools", "rag"], 12, null, 58, 2, ["vector-db", "hybrid-search"]],
  ["bug", "Memory leak in example-inference server streaming mode", "Fictional issue: RSS grows unbounded when clients disconnect mid-stream.", ["bugs", "llmops"], 7, "high", 66, 2, ["memory-leak", "inference"]],
  ["github_repo", "demo-org/agent-kit gains 4.1k stars this week", "Fictional repository ranked by stars gained between our own snapshots.", ["ai-agents"], 20, null, 55, 2, ["agents", "python"]],
  ["devops", "Kubernetes-like orchestrator v9.9 deprecates legacy API (demo)", "Fictional release notes announcing an API removal in the next minor version.", ["kubernetes", "devops"], 26, "medium", 48, 0, ["kubernetes", "deprecation"]],
  ["vulnerability", "CVE-0000-00002 privilege escalation in demo container runtime", "Fictional local privilege escalation in an imaginary runtime.", ["cybersecurity", "docker"], 30, "high", 81, 1, ["container", "privilege-escalation"]],
  ["github_issue", "demo-org/trainer #4821: NaN loss with mixed precision", "Fictional open issue reported against an imaginary training library.", ["mlops", "bugs"], 33, "medium", 42, 2, ["training", "fp16"]],
  ["news", "Example Labs publishes evaluation results for RAG benchmark", "Fictional benchmark comparing retrieval pipelines on synthetic questions.", ["rag", "ai-research"], 40, null, 61, 0, ["rag", "evaluation"]],
  ["model_release", "Fictional Corp ships Quill-Code 2 for code completion", "Imaginary code model update with improved repository-level context.", ["ai-models", "software-engineering"], 52, null, 69, 0, ["code", "llm"]],
  ["incident", "Demo AI API: degraded latency (resolved)", "Fictional provider reported slow responses; marked resolved on its status page.", ["infrastructure-failures"], 60, "medium", 45, 3, ["latency"]],
  ["vulnerability", "CVE-0000-00003 SSRF in demo dashboard plugin", "Fictional server-side request forgery in an imaginary plugin.", ["cybersecurity"], 70, "medium", 50, 1, ["ssrf"]],
  ["tool", "promptflowx 0.9: tracing for LLM apps (demo)", "Imaginary LLMOps tool adds OpenTelemetry tracing.", ["llmops", "ai-tools"], 80, null, 47, 2, ["observability", "llmops"]],
  ["research", "Agent self-verification reduces tool errors (demo paper)", "Made-up study of verification loops for tool-using agents.", ["ai-research", "ai-agents"], 96, null, 57, 0, ["agents", "evaluation"]],
  ["devops", "Demo registry adds signed image provenance", "Fictional container registry feature announcement.", ["docker", "devops"], 110, "info", 39, 0, ["supply-chain", "containers"]],
  ["bug", "Regression: demo ORM drops index on migration", "Fictional regression report with a fix merged in a patch release.", ["bugs", "software-engineering"], 130, "medium", 44, 2, ["regression", "database"]],
  ["vulnerability", "CVE-0000-00004 information disclosure in demo SDK", "Fictional low-severity information leak in debug logging.", ["cybersecurity"], 150, "low", 30, 1, ["logging"]],
  ["news", "Demo cloud provider launches managed vector search", "Fictional managed service announcement.", ["cloud", "rag"], 170, null, 52, 0, ["vector-db", "cloud"]],
  ["github_repo", "demo-org/kube-gpt trending in DevOps tooling", "Fictional repository ranked by stars gained between snapshots.", ["kubernetes", "ai-tools"], 190, null, 41, 2, ["kubernetes", "agents"]],
  ["model_release", "Example Labs Nimbus-1B for edge devices (demo)", "Fictional small model optimised for on-device inference.", ["ai-models"], 220, null, 49, 0, ["edge", "llm"]],
  ["incident", "Demo Git host: webhooks delayed (resolved)", "Fictional incident, resolved per the provider's status page.", ["infrastructure-failures", "devops"], 260, "low", 33, 3, ["webhooks"]],
];

const now = Date.now();
const iso = (hoursAgo: number) => new Date(now - hoursAgo * 3_600_000).toISOString();
const SEV_BASIS: Partial<Record<Severity, string>> = {
  critical: "Demo: vendor CVSS 9.8 (fictional)",
  high: "Demo: vendor-reported severity (fictional)",
  medium: "Demo: vendor-reported severity (fictional)",
  low: "Demo: vendor-reported severity (fictional)",
  info: "Demo: informational notice (fictional)",
};

const ARTICLES: Article[] = SEEDS.map(([type, title, desc, cats, hours, sev, imp, src, tags], i) => ({
  id: `demo-${i + 1}`,
  item_type: type,
  title: `[DEMO] ${title}`,
  description: desc,
  url: `https://example.com/demo/${i + 1}`,
  author: null,
  published_at: iso(hours),
  collected_at: iso(Math.max(hours - 0.5, 0.1)),
  verification_status: "official",
  severity: sev,
  severity_basis: sev ? (SEV_BASIS[sev] ?? null) : null,
  importance_score: imp,
  tags,
  source: SOURCES[src]!,
  categories: CATS.filter((c) => cats.includes(c.slug)),
  duplicate_of_id: null,
  is_bookmarked: i === 0 || i === 4,
  is_read: i % 3 === 2,
  ai_summary:
    i % 2 === 0
      ? {
          short: `Demo AI summary: ${desc.replace(/\.$/, "")} — this text is fictional and shows where AI-generated summaries will appear.`,
          provider: "demo",
          model: "demo-model",
          generated_at: iso(Math.max(hours - 1, 0.05)),
        }
      : null,
}));

const DEMO_USER: User = {
  id: "demo-user",
  email: "demo@example.com",
  full_name: "Demo User",
  is_active: true,
  role: "admin",
  created_at: iso(24 * 30),
  last_login_at: iso(1),
};

let prefs: Preferences = {
  interests: ["rag", "kubernetes", "cybersecurity"],
  followed_technologies: ["vLLM", "Kubernetes"],
  followed_repositories: ["demo-org/agent-kit"],
  followed_providers: ["Example Labs"],
  min_notification_severity: "high",
  briefing_frequency: "daily",
  briefing_hour: 7,
  briefing_weekday: 0,
  timezone: "UTC",
  theme: "dark",
  alert_settings: {
    critical_cves: true, exploited: true, critical_bugs: true, outages: true, watched_tech: true,
    min_cvss: null, outage_min_impact: "major", outage_providers: [], bug_projects: [],
    model_releases: true, model_providers: [], briefing_ready: true,
  },
};

const NOTIFS: Notification[] = [
  { id: "n1", kind: "vulnerability", severity: "critical", title: "[DEMO] New critical CVE affects a technology you follow", body: "CVE-0000-00001 (fictional)", article_id: "demo-3", link: "https://example.com/demo/3", created_at: iso(5.5), read_at: null },
  { id: "n2", kind: "incident", severity: "high", title: "[DEMO] Demo Cloud reports elevated error rates", body: null, article_id: "demo-4", link: "https://example.com/demo/4", created_at: iso(1.8), read_at: null },
  { id: "n3", kind: "model_release", severity: "info", title: "[DEMO] Nimbus-7B released by Example Labs", body: null, article_id: "demo-1", link: "https://example.com/demo/1", created_at: iso(2.9), read_at: iso(2) },
  { id: "n4", kind: "critical_alert", severity: "critical", title: "[DEMO] Actively exploited: CVE-0000-00002 added to the (fictional) KEV list", body: "[DEMO] Apply the vendor update.", article_id: "demo-3", link: "https://example.com/demo/3", created_at: iso(0.7), read_at: null },
  { id: "n5", kind: "briefing", severity: "info", title: "[DEMO] Your daily briefing is ready", body: "[DEMO] 9 highlighted items.", article_id: null, link: `/briefing?date=${new Date(now).toISOString().slice(0, 10)}`, created_at: iso(1), read_at: null },
];

const BRIEFING: Briefing = {
  id: "demo-briefing",
  user_id: "demo-user",
  briefing_date: new Date(now).toISOString().slice(0, 10),
  period_start: iso(24),
  period_end: iso(0),
  executive_summary:
    "[DEMO] Fictional briefing. A critical (fictional) HTTP library flaw and a cloud storage incident lead today, alongside a new open-weights model release and progress in long-context RAG.",
  sections: {
    top_ai: ARTICLES.filter((a) => ["model_release", "news"].includes(a.item_type)).slice(0, 3).map((a) => ({ article_id: a.id, title: a.title, url: a.url })),
    model_releases: ARTICLES.filter((a) => a.item_type === "model_release").slice(0, 2).map((a) => ({ article_id: a.id, title: a.title, url: a.url, source: a.source.name })),
    new_tools: ARTICLES.filter((a) => a.item_type === "tool").slice(0, 2).map((a) => ({ article_id: a.id, title: a.title, url: a.url })),
    research: ARTICLES.filter((a) => a.item_type === "research").slice(0, 2).map((a) => ({ article_id: a.id, title: a.title, url: a.url })),
    vulnerabilities: ARTICLES.filter((a) => a.item_type === "vulnerability").slice(0, 2).map((a) => ({ article_id: a.id, title: a.title, url: a.url })),
    bugs: ARTICLES.filter((a) => a.item_type === "bug").slice(0, 2).map((a) => ({ article_id: a.id, title: a.title, url: a.url, severity: a.severity, severity_basis: a.severity_basis })),
    incidents: ARTICLES.filter((a) => a.item_type === "incident").slice(0, 1).map((a) => ({ article_id: a.id, title: a.title, url: a.url, provider: "Demo Cloud", state: "current" as const, last_verified_at: iso(0.1) })),
    changes: [
      { kind: "count", title: "[DEMO] Critical vulnerabilities: 1 new since the last briefing", summary: "2 item(s) now vs 1 previously.", url: null },
      { kind: "followed", title: "[DEMO] Followed: Kubernetes ingress update", summary: "Mentions something you follow.", url: "https://example.com/demo/5" },
    ],
    learning: [{ title: "[DEMO] Study: hybrid retrieval (BM25 + vectors)", url: null, summary: "Several of today's items concern rag." }],
    meta: { interests: ["rag", "kubernetes"], followed_count: 4, frequency: "daily", timezone: "UTC", previous_briefing_date: null },
  },
  cited_article_ids: ["demo-1", "demo-3", "demo-4"],
  llm_provider: "demo",
  llm_model: "demo-model",
  generated_at: iso(1),
};

function page<T>(items: T[], p = 1, size = 20): Page<T> {
  const start = (p - 1) * size;
  return { items: items.slice(start, start + size), total: items.length, page: p, page_size: size, pages: Math.ceil(items.length / size) };
}

const asList = (v: unknown): string[] => (v == null ? [] : Array.isArray(v) ? v.map(String) : [String(v)]);
const when = (a: Article) => Date.parse(a.published_at ?? a.collected_at);

function filterArticles(q: Record<string, unknown> = {}): Article[] {
  let items = [...ARTICLES];
  const text = typeof q.q === "string" ? q.q.toLowerCase().trim() : "";
  if (text) {
    const words = text.split(/\s+/);
    items = items.filter((a) => words.every((w) => `${a.title} ${a.description ?? ""}`.toLowerCase().includes(w)));
  }
  const types = asList(q.item_type);
  if (types.length) items = items.filter((a) => types.includes(a.item_type));
  const cats = asList(q.category);
  if (cats.length) items = items.filter((a) => a.categories.some((c) => cats.includes(c.slug)));
  const srcs = asList(q.source);
  if (srcs.length) items = items.filter((a) => srcs.includes(a.source.slug));
  const sev = asList(q.severity);
  if (sev.length) items = items.filter((a) => a.severity && sev.includes(a.severity));
  if (q.min_importance != null) items = items.filter((a) => (a.importance_score ?? -1) >= Number(q.min_importance));
  if (q.date_from) items = items.filter((a) => when(a) >= Date.parse(String(q.date_from)));
  if (q.date_to) items = items.filter((a) => when(a) <= Date.parse(String(q.date_to)));
  if (q.sort === "importance") items.sort((a, b) => (b.importance_score ?? -1) - (a.importance_score ?? -1));
  else items.sort((a, b) => when(b) - when(a));
  return items;
}

function countBy(items: Article[], key: (a: Article) => string[]): { key: string; count: number }[] {
  const m = new Map<string, number>();
  items.forEach((a) => key(a).forEach((k) => m.set(k, (m.get(k) ?? 0) + 1)));
  return [...m.entries()].map(([k, count]) => ({ key: k, count })).sort((a, b) => b.count - a.count);
}

function summary(): DashboardSummary {
  const within = (h: number) => (a: Article) => now - when(a) <= h * 3_600_000;
  const activity = Array.from({ length: 14 }, (_, i) => {
    const d = new Date(now - (13 - i) * 86_400_000).toISOString().slice(0, 10);
    // Each fixture lands on its own day; pad with a deterministic shape so the chart has visible form.
    const real = ARTICLES.filter((a) => (a.published_at ?? "").startsWith(d)).length;
    return { day: d, count: real + ((i * 7) % 5) + 2 };
  });
  return {
    total_articles: ARTICLES.length,
    articles_last_24h: ARTICLES.filter(within(24)).length,
    model_releases_7d: ARTICLES.filter((a) => a.item_type === "model_release" && within(168)(a)).length,
    new_github_issues_7d: ARTICLES.filter((a) => a.item_type === "github_issue" && within(168)(a)).length,
    critical_vulnerabilities_7d: ARTICLES.filter((a) => a.item_type === "vulnerability" && a.severity === "critical" && within(168)(a)).length,
    known_exploited_7d: 0,
    active_incidents: 1,
    sources_enabled: SOURCES.length,
    sources_failing: 0,
    by_item_type: countBy(ARTICLES, (a) => [a.item_type]),
    by_category: countBy(ARTICLES, (a) => a.categories.map((c) => c.slug)),
    by_severity: countBy(ARTICLES.filter((a) => a.severity), (a) => [a.severity!]),
    trending_tags: countBy(ARTICLES.filter(within(168)), (a) => a.tags).slice(0, 12),
    activity_14d: activity,
    latest: filterArticles().slice(0, 8),
    latest_ai: filterArticles({ item_type: ["news", "model_release", "tool"] }).slice(0, 5),
    top_security: filterArticles({ item_type: ["vulnerability"], severity: ["critical", "high"] }).slice(0, 5),
    recent_failures: filterArticles({ item_type: ["bug", "incident"] }).slice(0, 5),
  };
}

const delay = () => new Promise((r) => setTimeout(r, 250));

export async function demoFetch<T>(
  path: string,
  method: string,
  query?: Record<string, unknown>,
  body?: BodyInit | null,
): Promise<T> {
  await delay();
  const q = query ?? {};
  const json = typeof body === "string" ? (JSON.parse(body) as Record<string, unknown>) : {};
  const art = path.match(/^\/(?:news|bookmarks)\/([^/]+)/)?.[1];
  const r = <R>(v: R) => v as unknown as T;

  if (path === "/auth/refresh" || path === "/auth/login") return r({ access_token: "demo", token_type: "bearer", expires_in: 900 });
  if (path === "/auth/me") return r(DEMO_USER);
  if (path === "/auth/logout") return r({ message: "Logged out (demo)" });
  if (path.startsWith("/auth/")) return r({ message: "Demo mode: no changes were made." });
  if (path === "/dashboard/summary") return r(summary());
  if (path === "/categories") return r(CATS);
  if (path === "/sources") return r(SOURCES);
  if (path === "/news") return r(page(filterArticles(q), Number(q.page ?? 1), Number(q.page_size ?? 20)));
  if (path.endsWith("/analysis") && art) {
    const a = ARTICLES.find((x) => x.id === art);
    return r({
      article_id: art,
      ai_generated_notice: "Summary, impact and recommendations are AI-generated from the original source.",
      summary: a?.ai_summary
        ? {
            short_summary: a.ai_summary.short, detailed_explanation: "[DEMO] Fictional detailed explanation.",
            what_happened: `[DEMO] ${a.description}`, why_it_matters: "[DEMO] Shows where the impact explanation appears.",
            who_is_affected: "[DEMO] Fictional users of the fictional product.",
            technical_impact: { level: "medium", description: "[DEMO] Fictional impact assessment." },
            recommended_actions: ["[DEMO] Review the vendor advisory."], related_technologies: a.tags,
            learning_resources: [{ title: "Kubernetes documentation", url: "https://kubernetes.io/docs/home/", source: "curated" }],
            source_references: [a.url], unsupported_claims_removed: [], actions_removed: [],
          }
        : null,
      summary_status: a?.ai_summary
        ? { status: "ready", provider: "demo", model: "demo-model", generated_at: a.ai_summary.generated_at, error: null }
        : { status: "pending", provider: null, model: null, generated_at: null, error: null },
      importance: {
        score: a?.importance_score ?? 50, label: "AI Pulse importance (0-100). Not an official CVSS score.", version: "importance-v1",
        factors: [
          { name: "source_reliability", value: 0.9, weight: 0.24, contribution: 21.6, reason: "Source reliability 0.90" },
          { name: "severity", value: 0.6, weight: 0.29, contribution: 17.4, reason: "[DEMO] Fictional severity" },
          { name: "recency", value: 0.8, weight: 0.18, contribution: 14.4, reason: "Recently published" },
          { name: "verification", value: 1, weight: 0.12, contribution: 12, reason: "Verification: official" },
        ],
        excluded: ["technical_impact"], personal_score: null, personal_reasons: [],
      },
      language: "en", keywords: a?.tags ?? [], entities: [],
    });
  }
  if (path.endsWith("/read") && art) {
    const a = ARTICLES.find((x) => x.id === art);
    if (a) a.is_read = method === "PUT";
    return r(undefined);
  }
  if (path.startsWith("/news/") && art) return r(ARTICLES.find((a) => a.id === art));
  if (path === "/bookmarks") {
    const items: Bookmark[] = ARTICLES.filter((a) => a.is_bookmarked).map((a) => ({ id: `b-${a.id}`, note: null, created_at: a.collected_at, article: a }));
    return r(page(items, Number(q.page ?? 1), Number(q.page_size ?? 20)));
  }
  if (path.startsWith("/bookmarks/") && art) {
    const a = ARTICLES.find((x) => x.id === art);
    if (a) a.is_bookmarked = method === "PUT";
    return r(undefined);
  }
  if (path === "/notifications/unread-count") {
    const unread = NOTIFS.filter((n) => !n.read_at);
    const by_kind: Record<string, number> = {};
    unread.forEach((n) => (by_kind[n.kind] = (by_kind[n.kind] ?? 0) + 1));
    return r({ unread: unread.length, by_kind });
  }
  if (path === "/notifications/read-all") {
    const kinds = asList(q.kind);
    NOTIFS.forEach((n) => {
      if (!kinds.length || kinds.includes(n.kind)) n.read_at ??= new Date().toISOString();
    });
    return r(undefined);
  }
  if (path.startsWith("/notifications/")) {
    const idx = NOTIFS.findIndex((x) => path.split("/")[2] === x.id);
    const n = NOTIFS[idx];
    if (n && method === "DELETE") NOTIFS.splice(idx, 1);
    else if (n && path.endsWith("/unread")) n.read_at = null;
    else if (n) n.read_at ??= new Date().toISOString();
    return r(undefined);
  }
  if (path === "/notifications") {
    const kinds = asList(q.kind);
    let items = q.unread_only ? NOTIFS.filter((n) => !n.read_at) : NOTIFS;
    if (kinds.length) items = items.filter((n) => kinds.includes(n.kind));
    return r(page(items, Number(q.page ?? 1), Number(q.page_size ?? 20)));
  }
  if (path === "/preferences/follow" || path === "/preferences/unfollow") {
    const field = ({ technology: "followed_technologies", repository: "followed_repositories", provider: "followed_providers" } as const)[json.type as "technology" | "repository" | "provider"];
    const value = String(json.value ?? "").trim();
    const list = prefs[field].filter((v) => v.toLowerCase() !== value.toLowerCase());
    prefs = { ...prefs, [field]: path.endsWith("/follow") ? [...list, value] : list };
    return r(prefs);
  }
  if (path === "/preferences/options") return r({ interests: ["ai-engineering", "generative-ai", "rag", "ai-agents", "llmops", "devops", "cloud", "kubernetes", "cybersecurity", "software-engineering"] });
  if (path === "/preferences") {
    if (method === "PUT") prefs = { ...prefs, ...json } as Preferences;
    return r(prefs);
  }
  if (path === "/radar/summary") {
    const days = Array.from({ length: 31 }, (_, i) => ({ day: new Date(now - (30 - i) * 86_400_000).toISOString().slice(0, 10), total: (i * 5) % 4, by_provider: {} }));
    return r({
      generated_at: iso(0), window_days: 30, critical_bugs: [], new_vulnerabilities: [], newly_exploited: [],
      active_incidents: [], resolved_incidents: [], unverified_incidents: 0,
      severity_chart: [{ key: "critical", count: 1 }, { key: "high", count: 1 }, { key: "medium", count: 1 }, { key: "low", count: 1 }],
      most_affected: [{ name: "[demo] example-http", vulnerabilities: 2, bugs: 1, incidents: 0, total: 3 }],
      incident_history: days,
      weekly: Array.from({ length: 8 }, (_, i) => ({ week_start: new Date(now - (7 - i) * 7 * 86_400_000).toISOString().slice(0, 10), incidents: i % 3, outage_minutes: (i % 3) * 45, critical_high_cves: i + 2, kev_added: i % 2, bugs_reported: i, bugs_fixed: i % 2 })),
    });
  }
  if (path === "/bugs" || path === "/security/vulnerabilities") return r(page([]));
  if (path === "/incidents") {
    const items: RadarIncident[] = [
      { state: "current", categories: ["cloud"], duration_minutes: null, id: "demo-inc-1", provider: "Demo Cloud", external_id: "demo-1", title: "[DEMO] Elevated API error rates in region demo-east-1", affected_services: ["Object storage API"], regions: ["demo-east-1"], status: "investigating", impact: "major", started_at: iso(2), resolved_at: null, status_page_url: "https://example.com/demo/status/1", last_verified_at: iso(0.1), article_id: "demo-4", is_active: true, status_is_stale: false },
    ];
    return r(page(q.active_only ? items.filter((i) => i.is_active) : items));
  }
  if (path === "/security/stats") return r({ total: 4, by_severity: { critical: 1, high: 1, medium: 1, low: 1 }, known_exploited: 0, published_last_7d: 2, critical_last_7d: 1 });
  if (path === "/github/repositories") {
    const repos: GitHubRepository[] = [
      { id: "demo-repo-1", full_name: "demo-org/agent-kit", description: "[DEMO] Fictional agent toolkit", html_url: "https://example.com/demo/repo/1", language: "Python", topics: ["agents"], stars: 18200, forks: 900, open_issues: 120, stars_delta_7d: 4100, latest_release: "v0.9.0", latest_release_at: iso(48), pushed_at: iso(3), tracked: true, updated_at: iso(1) },
      { id: "demo-repo-2", full_name: "demo-org/kube-gpt", description: "[DEMO] Fictional Kubernetes assistant", html_url: "https://example.com/demo/repo/2", language: "Go", topics: ["kubernetes"], stars: 6400, forks: 310, open_issues: 45, stars_delta_7d: 1250, latest_release: "v1.2.0", latest_release_at: iso(120), pushed_at: iso(10), tracked: true, updated_at: iso(2) },
    ];
    return r(page(repos));
  }
  if (path === "/models") {
    const models: AIModel[] = [
      { id: "demo-model-1", provider: "Example Labs (demo)", name: "Nimbus-7B", family: "Nimbus", modality: ["text"], is_open_weights: true, homepage_url: null, created_at: iso(500), updated_at: iso(3), latest_release: { id: "demo-rel-1", version: "1.0", released_at: iso(3), context_window: 131072, notes: null, source_url: "https://example.com/demo/1", article_id: "demo-1" }, release_count: 1 },
      { id: "demo-model-2", provider: "Fictional Corp (demo)", name: "Quill-Code 2", family: "Quill", modality: ["text", "code"], is_open_weights: false, homepage_url: null, created_at: iso(900), updated_at: iso(52), latest_release: { id: "demo-rel-2", version: "2", released_at: iso(52), context_window: null, notes: null, source_url: "https://example.com/demo/13", article_id: "demo-13" }, release_count: 2 },
    ];
    return r(page(models));
  }
  if (path === "/search") {
    const hits = filterArticles({ ...q, sort: "latest", item_type: q.item_type }).map((a) => ({ article: a, rank: 0.5, snippet: a.description ? `[[${a.description.split(" ")[0]}]] ${a.description.split(" ").slice(1).join(" ")}` : null }));
    const res = page(hits, Number(q.page ?? 1), 20);
    return r({ ...res, query: String(q.q ?? ""), mode: "keyword" });
  }
  if (path === "/admin/ingestion/status") {
    const mk = (i: number, name: string, connector: string, health: SourceStatus["health"], err: string | null = null): SourceStatus => ({
      id: `demo-src-${i}`, slug: `demo-${i}`, name: `[DEMO] ${name}`, connector, source_type: "api", url: "https://example.com/demo/feed",
      enabled: health !== "disabled", is_official: true, poll_interval_minutes: 60, health,
      health_reason: health === "failing" ? "3 consecutive failed runs" : health === "disabled" ? "Disabled by an administrator" : "Collecting normally",
      consecutive_failures: health === "failing" ? 3 : 0, last_success_at: health === "failing" ? iso(30) : iso(0.5), last_error_at: err ? iso(0.2) : null,
      last_error: err, next_run_at: health === "disabled" ? null : iso(-0.5),
      last_job: { id: `demo-job-${i}`, source_id: `demo-src-${i}`, status: err ? "failed" : "succeeded", trigger: "schedule", started_at: iso(0.5),
        finished_at: iso(0.49), duration_seconds: 2.4, items_fetched: 40, items_created: err ? 0 : 6, items_updated: 1, items_skipped: 33, attempt: 1, error: err, errors: [] },
      items_total: 400 + i * 37, items_24h: err ? 0 : 6 + i,
    });
    const sources = [mk(1, "Vendor blog", "rss", "healthy"), mk(2, "Advisory API", "nvd", "healthy"), mk(3, "Status page", "statuspage", "failing", "FetchError: HTTP 503 from example.com after 4 attempts"), mk(4, "Paused feed", "rss", "disabled")];
    return r({ generated_at: iso(0), totals: { sources: 4, enabled: 3, items: 1600, items_24h: 21 }, by_health: { healthy: 2, failing: 1, disabled: 1 },
      sources, recent_failures: sources.filter((x) => x.last_job?.status === "failed").map((x) => x.last_job!) });
  }
  if (path === "/admin/ai/status") return r({ llm_provider: "demo", llm_model: "demo-model", embedding_provider: null, embedding_model: null, problems: ["[DEMO] fictional status"], items_total: ARTICLES.length, items_with_rules_analysis: ARTICLES.length, items_with_ai_summary: 12, items_with_embedding: 0, failed_analyses: 0, tokens_today: 0, cost_today_usd: null, calls_today: 0, errors_today: 0 });
  if (method === "GET" && path.startsWith("/admin/")) {
    const days = (n: number, f: (i: number) => number) =>
      Array.from({ length: n + 1 }, (_, i) => ({ day: new Date(now - (n - i) * 86_400_000).toISOString().slice(0, 10), value: f(i) }));
    const n = Number(q.days ?? 30);
    if (path === "/admin/system/health")
      return r({
        status: "degraded", environment: "demo", version: "0.8.0", started_at: iso(30), checked_at: iso(0),
        checks: [
          { name: "database", status: "ok", detail: null, latency_ms: 2.1, data: { postgres: "16 (demo)", pgvector: "0.8", connections: 9, max_connections: 100 } },
          { name: "migrations", status: "ok", detail: null, latency_ms: null, data: { current: "0006", head: "0006" } },
          { name: "redis", status: "ok", detail: null, latency_ms: 0.4, data: { used_memory: "1.1M", queues: { ingestion: 0 } } },
          { name: "scheduler", status: "ok", detail: null, latency_ms: null, data: { last_dispatch_at: iso(0.01) } },
          { name: "workers", status: "ok", detail: null, latency_ms: null, data: { last_task_success_at: iso(0.05) } },
          { name: "ingestion", status: "degraded", detail: "[DEMO] 1 of 27 sources failing", latency_ms: null, data: { enabled_sources: 27, failing_sources: ["demo-feed"], failed_jobs_24h: 2, running_jobs: 0 } },
          { name: "ai_provider", status: "ok", detail: null, latency_ms: null, data: { provider: "demo", calls_24h: 40, errors_24h: 1 } },
        ],
      });
    if (path === "/admin/usage")
      return r({
        window_days: n, generated_at: iso(0), users_total: 4, users_active: 4, users_by_role: { admin: 1, analyst: 1, user: 2 },
        users_new: 2, users_logged_in_7d: 3, signups_by_day: days(n, (i) => (i % 9 === 0 ? 1 : 0)),
        articles_total: ARTICLES.length, articles_by_day: days(n, (i) => 20 + ((i * 7) % 13)), articles_by_type: { news: 8, vulnerability: 4, research: 3 },
        bookmarks_total: 3, notifications_by_day: days(n, (i) => i % 4), notifications_by_kind: { vulnerability: 6, model_release: 3, briefing: 5 },
        notifications_read_ratio: 0.6, briefings_by_day: days(n, () => 1),
        ai_by_day: days(n, (i) => i).map((d) => ({ day: d.day, calls: 30, errors: d.value % 5 === 0 ? 1 : 0, tokens: 12000 + d.value * 150, cost_usd: null })),
        ai_by_model: [{ provider: "demo", model: "demo-model", purpose: "analysis", calls: 900, errors: 6, input_tokens: 300000, output_tokens: 60000, cost_usd: null }],
        ai_tokens_total: 360000, ai_cost_total_usd: null, ai_daily_token_budget: 200000,
      });
    if (path === "/admin/ai/config")
      return r({ llm_provider: "demo", llm_model: "demo-model", embedding_provider: "none", embedding_model: null, embedding_dim: 768,
        openai_base_url: "https://api.openai.com/v1", anthropic_api_url: "https://api.anthropic.com", ollama_base_url: "http://localhost:11434",
        openai_api_key_set: false, anthropic_api_key_set: false, llm_timeout_seconds: 90, llm_max_output_tokens: 1800, llm_temperature: 0.2,
        llm_price_input_per_mtok: null, llm_price_output_per_mtok: null, ai_batch_size: 20, ai_daily_token_budget: 200000 });
    if (path === "/admin/roles")
      return r([{ id: 1, name: "admin", description: null, user_count: 1 }, { id: 2, name: "analyst", description: null, user_count: 1 }, { id: 3, name: "user", description: null, user_count: 2 }]);
    if (path === "/admin/users")
      return r(page([
        { id: "demo-user", email: "demo@example.com", full_name: "[DEMO] Admin", is_active: true, role: "admin", created_at: iso(900), last_login_at: iso(1), updated_at: iso(1) },
        { id: "u2", email: "analyst@example.com", full_name: "[DEMO] Analyst", is_active: true, role: "analyst", created_at: iso(400), last_login_at: iso(30), updated_at: iso(30) },
        { id: "u3", email: "reader@example.com", full_name: null, is_active: false, role: "user", created_at: iso(200), last_login_at: null, updated_at: iso(50) },
      ]));
    if (path === "/admin/jobs")
      return r(page([
        { id: "j1", source_id: "s1", source: { id: "s1", slug: "demo-feed", name: "[DEMO] Example feed" }, status: "failed", trigger: "schedule", celery_task_id: null, started_at: iso(2), finished_at: iso(1.99), duration_seconds: 4.2, items_fetched: 0, items_created: 0, items_updated: 0, items_skipped: 0, attempt: 3, error: "[DEMO] HTTP 503 from the (fictional) feed", errors: [] },
        { id: "j2", source_id: "s2", source: { id: "s2", slug: "demo-nvd", name: "[DEMO] CVE feed" }, status: "succeeded", trigger: "schedule", celery_task_id: null, started_at: iso(3), finished_at: iso(2.98), duration_seconds: 61.5, items_fetched: 120, items_created: 14, items_updated: 3, items_skipped: 103, attempt: 1, error: null, errors: [] },
      ]));
    if (path === "/admin/audit-logs")
      return r(page([{ id: "a1", actor_id: "demo-user", actor_email: "demo@example.com", action: "source.update", target_type: "source", target_id: "s1", details: { enabled: false }, ip_address: "127.0.0.1", created_at: iso(5) }]));
    if (path === "/admin/sources")
      return r([{ id: "s1", slug: "demo-feed", name: "[DEMO] Example feed", source_type: "rss", connector: "rss", url: "https://example.com/feed.xml", homepage_url: null, default_item_type: "news", is_official: true, reliability: 0.9, enabled: true, poll_interval_minutes: 60, config: {}, last_success_at: iso(26), last_error_at: iso(2), last_error: "[DEMO] HTTP 503", consecutive_failures: 3, created_at: iso(900) }]);
    if (path === "/admin/connectors") return r([{ key: "rss", description: "[DEMO] RSS / Atom feeds", config_schema: { properties: {} } }]);
  }
  if (path.startsWith("/admin/")) return r({ task_id: "demo-task", message: "Demo mode: no changes were made." });
  if (path === "/search/capabilities") return r({ keyword: true, semantic: false, hybrid: false, ask: true, ask_mode: "sources-only", embedded_items: 0, total_items: ARTICLES.length });
  if (path === "/search/ask") {
    const sources = ARTICLES.slice(0, 3).map((a, i) => ({ n: i + 1, article_id: a.id, title: a.title, url: a.url, source: a.source.name,
      item_type: a.item_type, published_at: a.published_at, importance: a.importance_score, relevance: {}, ai_summary: null }));
    return r({ question: String(json.question ?? ""), answer: "[DEMO] This fictional answer cites its sources [1][2].", insufficient: false,
      reason: null, citations: sources.slice(0, 2), sources, unsupported_claims_removed: [],
      retrieval: { mode: "demo", item_types: [], date_from: null, terms: [] }, generated_by: { provider: "demo", model: "demo-model" }, confidence: "low" });
  }
  if (path === "/briefings/generate") return r(BRIEFING);
  if (path === "/briefings/latest" || path === `/briefings/${BRIEFING.briefing_date}`) return r(BRIEFING);
  if (path === "/briefings") {
    const list: BriefingListItem[] = [{ id: BRIEFING.id, briefing_date: BRIEFING.briefing_date, executive_summary: BRIEFING.executive_summary, generated_at: BRIEFING.generated_at, personalized: true }];
    return r(list);
  }
  throw new Error(`Demo mode: no fixture for ${method} ${path}`);
}
