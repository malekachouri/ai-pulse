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
  Incident,
  ItemType,
  Notification,
  Page,
  Preferences,
  Severity,
  SourceBrief,
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
  timezone: "UTC",
  theme: "dark",
};

const NOTIFS: Notification[] = [
  { id: "n1", kind: "vulnerability", severity: "critical", title: "[DEMO] New critical CVE affects a technology you follow", body: "CVE-0000-00001 (fictional)", article_id: "demo-3", link: "https://example.com/demo/3", created_at: iso(5.5), read_at: null },
  { id: "n2", kind: "incident", severity: "high", title: "[DEMO] Demo Cloud reports elevated error rates", body: null, article_id: "demo-4", link: "https://example.com/demo/4", created_at: iso(1.8), read_at: null },
  { id: "n3", kind: "model_release", severity: "info", title: "[DEMO] Nimbus-7B released by Example Labs", body: null, article_id: "demo-1", link: "https://example.com/demo/1", created_at: iso(2.9), read_at: iso(2) },
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
    new_tools: ARTICLES.filter((a) => a.item_type === "tool").slice(0, 2).map((a) => ({ article_id: a.id, title: a.title, url: a.url })),
    research: ARTICLES.filter((a) => a.item_type === "research").slice(0, 2).map((a) => ({ article_id: a.id, title: a.title, url: a.url })),
    vulnerabilities: ARTICLES.filter((a) => a.item_type === "vulnerability").slice(0, 2).map((a) => ({ article_id: a.id, title: a.title, url: a.url })),
    incidents: ARTICLES.filter((a) => a.item_type === "incident").slice(0, 1).map((a) => ({ article_id: a.id, title: a.title, url: a.url })),
    learning: "[DEMO] Review hybrid retrieval (BM25 + vectors) and container runtime hardening.",
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
  if (path === "/notifications/unread-count") return r({ unread: NOTIFS.filter((n) => !n.read_at).length });
  if (path === "/notifications/read-all") {
    NOTIFS.forEach((n) => (n.read_at ??= new Date().toISOString()));
    return r(undefined);
  }
  if (path.startsWith("/notifications/")) {
    const n = NOTIFS.find((x) => path.includes(x.id));
    if (n) n.read_at ??= new Date().toISOString();
    return r(undefined);
  }
  if (path === "/notifications") return r(page(q.unread_only ? NOTIFS.filter((n) => !n.read_at) : NOTIFS));
  if (path === "/preferences/options") return r({ interests: ["ai-engineering", "generative-ai", "rag", "ai-agents", "llmops", "devops", "cloud", "kubernetes", "cybersecurity", "software-engineering"] });
  if (path === "/preferences") {
    if (method === "PUT") prefs = { ...prefs, ...json } as Preferences;
    return r(prefs);
  }
  if (path === "/incidents") {
    const items: Incident[] = [
      { id: "demo-inc-1", provider: "Demo Cloud", external_id: "demo-1", title: "[DEMO] Elevated API error rates in region demo-east-1", affected_services: ["Object storage API"], regions: ["demo-east-1"], status: "investigating", impact: "major", started_at: iso(2), resolved_at: null, status_page_url: "https://example.com/demo/status/1", last_verified_at: iso(0.1), article_id: "demo-4", is_active: true, status_is_stale: false },
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
  if (path === "/briefings/latest") return r(BRIEFING);
  if (path === "/briefings") {
    const list: BriefingListItem[] = [{ id: BRIEFING.id, briefing_date: BRIEFING.briefing_date, executive_summary: BRIEFING.executive_summary, generated_at: BRIEFING.generated_at, personalized: true }];
    return r(list);
  }
  throw new Error(`Demo mode: no fixture for ${method} ${path}`);
}
