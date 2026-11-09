// Mirrors the FastAPI schemas in backend/app/schemas.

export type ItemType =
  | "news" | "model_release" | "tool" | "research" | "github_repo" | "github_issue"
  | "bug" | "vulnerability" | "incident" | "devops";
export type Severity = "critical" | "high" | "medium" | "low" | "info" | "unknown";
export type VerificationStatus = "official" | "verified" | "unverified" | "disputed";
export type SortOrder = "latest" | "importance" | "relevance";
export type Role = "admin" | "analyst" | "user";

export interface SourceBrief {
  id: string;
  slug: string;
  name: string;
  source_type: string;
  is_official: boolean;
  reliability: number;
}

export interface Category {
  id: number;
  slug: string;
  name: string;
}

export interface AISummary {
  short: string;
  provider: string;
  model: string;
  generated_at: string;
}

export interface Article {
  id: string;
  item_type: ItemType;
  title: string;
  description: string | null;
  url: string;
  author: string | null;
  published_at: string | null;
  collected_at: string;
  verification_status: VerificationStatus;
  severity: Severity | null;
  severity_basis: string | null;
  importance_score: number | null;
  tags: string[];
  source: SourceBrief;
  categories: Category[];
  duplicate_of_id: string | null;
  is_bookmarked: boolean;
  is_read: boolean;
  ai_summary: AISummary | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface CountByKey {
  key: string;
  count: number;
}

export interface DashboardSummary {
  total_articles: number;
  articles_last_24h: number;
  model_releases_7d: number;
  new_github_issues_7d: number;
  critical_vulnerabilities_7d: number;
  known_exploited_7d: number;
  active_incidents: number;
  sources_enabled: number;
  sources_failing: number;
  by_item_type: CountByKey[];
  by_category: CountByKey[];
  by_severity: CountByKey[];
  trending_tags: CountByKey[];
  activity_14d: { day: string; count: number }[];
  latest: Article[];
  latest_ai: Article[];
  top_security: Article[];
  recent_failures: Article[];
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  role: Role;
  created_at: string;
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface Bookmark {
  id: string;
  note: string | null;
  created_at: string;
  article: Article;
}

export type NotificationKind = "critical_alert" | "model_release" | "vulnerability" | "bug" | "incident" | "briefing" | "system";

export interface Notification {
  id: string;
  kind: NotificationKind;
  severity: Severity;
  title: string;
  body: string | null;
  article_id: string | null;
  link: string | null;
  created_at: string;
  read_at: string | null;
}

export interface UnreadCount {
  unread: number;
  by_kind: Partial<Record<NotificationKind, number>>;
}

export type FollowType = "technology" | "repository" | "provider";

export type BriefingFrequency = "daily" | "weekdays" | "weekly" | "off";

export interface Preferences {
  interests: string[];
  followed_technologies: string[];
  followed_repositories: string[];
  followed_providers: string[];
  min_notification_severity: Severity;
  briefing_frequency: BriefingFrequency;
  briefing_hour: number;
  briefing_weekday: number;
  timezone: string;
  theme: string;
  alert_settings: AlertSettings;
}

export interface BriefingSectionItem {
  article_id?: string | null;
  title: string;
  url?: string | null;
  summary?: string | null;
  source?: string;
  importance?: number | null;
  personal_score?: number;
  why_for_you?: string[];
  summary_is_ai?: boolean;
  severity?: string | null;
  severity_basis?: string | null;
  item_type?: string;
  published_at?: string | null;
  // vulnerabilities
  cve_id?: string;
  cvss?: number | null;
  known_exploited?: boolean;
  // incidents
  provider?: string;
  state?: "current" | "historical" | "unverified";
  status?: string;
  last_verified_at?: string;
  // changes / learning
  kind?: "count" | "resolved" | "exploited" | "followed";
}

export interface BriefingMeta {
  interests: string[];
  followed_count: number;
  frequency: BriefingFrequency;
  timezone: string;
  previous_briefing_date: string | null;
}

export interface Briefing {
  id: string;
  user_id: string | null;
  briefing_date: string;
  period_start: string;
  period_end: string;
  executive_summary: string | null;
  sections: Record<string, BriefingSectionItem[] | string | BriefingMeta>;
  cited_article_ids: string[];
  llm_provider: string | null;
  llm_model: string | null;
  generated_at: string;
}

export interface BriefingListItem {
  id: string;
  briefing_date: string;
  executive_summary: string | null;
  generated_at: string;
  personalized: boolean;
}

export interface ArticleFilters {
  q?: string;
  item_type?: ItemType[];
  category?: string[];
  source?: string[];
  severity?: Severity[];
  min_importance?: number;
  date_from?: string;
  date_to?: string;
  sort?: SortOrder;
  page?: number;
  page_size?: number;
}

// ---- Typed intelligence modules (Phase 3) ----

export type IncidentStatus = "investigating" | "identified" | "monitoring" | "resolved" | "unknown";

export interface Incident {
  id: string;
  provider: string;
  external_id: string;
  title: string;
  affected_services: string[];
  regions: string[];
  status: IncidentStatus;
  impact: string | null;
  started_at: string | null;
  resolved_at: string | null;
  status_page_url: string;
  last_verified_at: string;
  article_id: string | null;
  is_active: boolean;
  status_is_stale: boolean;
}

export interface SecurityStats {
  total: number;
  by_severity: Record<string, number>;
  known_exploited: number;
  published_last_7d: number;
  critical_last_7d: number;
}

export interface GitHubRepository {
  id: string;
  full_name: string;
  description: string | null;
  html_url: string;
  language: string | null;
  topics: string[];
  stars: number;
  forks: number;
  open_issues: number;
  stars_delta_7d: number | null;
  latest_release: string | null;
  latest_release_at: string | null;
  pushed_at: string | null;
  tracked: boolean;
  updated_at: string;
}

export interface ModelRelease {
  id: string;
  version: string | null;
  released_at: string | null;
  context_window: number | null;
  notes: string | null;
  source_url: string;
  article_id: string | null;
}

export interface AIModel {
  id: string;
  provider: string;
  name: string;
  family: string | null;
  modality: string[];
  is_open_weights: boolean | null;
  homepage_url: string | null;
  created_at: string;
  updated_at: string;
  latest_release: ModelRelease | null;
  release_count: number;
}

export interface SearchHit {
  article: Article;
  rank: number;
  snippet: string | null;
}

export interface SearchResponse {
  query: string;
  mode: "keyword" | "semantic" | "hybrid";
  items: SearchHit[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// ---- Ingestion (Phase 4) ----
export type SourceHealth = "disabled" | "never_run" | "healthy" | "degraded" | "failing" | "stale";
export type JobStatus = "pending" | "running" | "succeeded" | "failed" | "partial";

export interface CollectionJob {
  id: string;
  source_id: string;
  status: JobStatus;
  trigger: string;
  started_at: string;
  finished_at: string | null;
  duration_seconds: number | null;
  items_fetched: number;
  items_created: number;
  items_updated: number;
  items_skipped: number;
  attempt: number;
  error: string | null;
  errors: { stage?: string; error?: string; ref?: string | null }[];
}

export interface SourceStatus {
  id: string;
  slug: string;
  name: string;
  connector: string;
  source_type: string;
  url: string;
  enabled: boolean;
  is_official: boolean;
  poll_interval_minutes: number;
  health: SourceHealth;
  health_reason: string;
  consecutive_failures: number;
  last_success_at: string | null;
  last_error_at: string | null;
  last_error: string | null;
  last_job: CollectionJob | null;
  next_run_at: string | null;
  items_total: number;
  items_24h: number;
}

export interface IngestionOverview {
  generated_at: string;
  totals: { sources: number; enabled: number; items: number; items_24h: number };
  by_health: Partial<Record<SourceHealth, number>>;
  sources: SourceStatus[];
  recent_failures: CollectionJob[];
}

// ---- AI engine (Phase 5) ----
export interface ImportanceFactor {
  name: string;
  value: number;
  weight: number;
  contribution: number;
  reason: string;
}

export interface ImportanceBreakdown {
  score: number;
  label: string;
  version: string;
  factors: ImportanceFactor[];
  excluded: string[];
  personal_score: number | null;
  personal_reasons: string[];
}

export interface AISummaryFull {
  short_summary: string;
  detailed_explanation: string;
  what_happened: string;
  why_it_matters: string;
  who_is_affected: string;
  technical_impact: { level: string; description: string };
  recommended_actions: string[];
  related_technologies: string[];
  learning_resources: { title: string; url: string | null; source: string }[];
  source_references: string[];
  unsupported_claims_removed: string[];
  actions_removed: string[];
}

export interface ArticleAnalysis {
  article_id: string;
  ai_generated_notice: string;
  summary: AISummaryFull | null;
  summary_status: { status: "ready" | "pending" | "failed" | "disabled"; provider: string | null; model: string | null; generated_at: string | null; error: string | null };
  importance: ImportanceBreakdown | null;
  language: string | null;
  keywords: string[];
  entities: { type: string; value: string }[];
}

export interface SearchCapabilities {
  keyword: boolean;
  semantic: boolean;
  hybrid: boolean;
  ask: boolean;
  ask_mode: "generative" | "sources-only";
  embedded_items: number;
  total_items: number;
}

export interface AskCitation {
  n: number;
  article_id: string;
  title: string;
  url: string;
  source: string;
  item_type: ItemType;
  published_at: string | null;
  importance: number | null;
  relevance: Record<string, number>;
  ai_summary: string | null;
}

export interface AskResponse {
  question: string;
  answer: string | null;
  insufficient: boolean;
  reason: string | null;
  citations: AskCitation[];
  sources: AskCitation[];
  unsupported_claims_removed: string[];
  retrieval: { mode: string; item_types: string[]; date_from: string | null; terms: string[]; term_coverage?: number };
  generated_by: { provider: string; model: string } | null;
  confidence: string | null;
}

export interface AIStatus {
  llm_provider: string | null;
  llm_model: string | null;
  embedding_provider: string | null;
  embedding_model: string | null;
  problems: string[];
  items_total: number;
  items_with_rules_analysis: number;
  items_with_ai_summary: number;
  items_with_embedding: number;
  failed_analyses: number;
  tokens_today: number;
  cost_today_usd: number | null;
  calls_today: number;
  errors_today: number;
}

// ---- Bugs & Failures Radar (Phase 6) ----
export type BugResolution = "fixed" | "completed" | "not_planned" | "duplicate" | "unknown";

export interface SoftwareBug {
  id: string;
  title: string;
  project: string;
  kind: "bug" | "regression" | "performance" | "compatibility" | "security" | "other";
  severity: Severity;
  severity_basis: string | null;
  status: "open" | "closed";
  resolution: BugResolution | null;
  affected_versions: string[];
  fixed_in_version: string | null;
  fix_url: string | null;
  fix_merged_at: string | null;
  source_url: string;
  issue_number: number | null;
  repository: string | null;
  labels: string[];
  opened_at: string | null;
  source_updated_at: string | null;
  last_verified_at: string | null;
}

export interface Vulnerability {
  id: string;
  cve_id: string;
  description: string | null;
  cvss_score: number | null;
  cvss_version: string | null;
  cvss_vector: string | null;
  severity: Severity;
  cwe_ids: string[];
  affected_products: { vendor?: string; product?: string; ecosystem?: string; vulnerable_range?: string; patched?: string; version?: string }[];
  known_exploited: boolean;
  kev_date_added: string | null;
  kev_due_date: string | null;
  patch_available: boolean | null;
  remediation: string | null;
  references: { url: string; source?: string; tags?: string[] }[];
  published_at: string | null;
  last_modified_at: string | null;
  last_verified_at: string | null;
}

export interface RadarIncident extends Incident {
  state: "current" | "historical" | "unverified";
  categories: string[];
  duration_minutes: number | null;
}

export interface RadarSummary {
  generated_at: string;
  window_days: number;
  critical_bugs: SoftwareBug[];
  new_vulnerabilities: Vulnerability[];
  newly_exploited: Vulnerability[];
  active_incidents: RadarIncident[];
  resolved_incidents: RadarIncident[];
  unverified_incidents: number;
  severity_chart: CountByKey[];
  most_affected: { name: string; vulnerabilities: number; bugs: number; incidents: number; total: number }[];
  incident_history: { day: string; total: number; by_provider: Record<string, number> }[];
  weekly: { week_start: string; incidents: number; outage_minutes: number; critical_high_cves: number; kev_added: number; bugs_reported: number; bugs_fixed: number }[];
}

export interface AlertSettings {
  critical_cves: boolean;
  exploited: boolean;
  critical_bugs: boolean;
  outages: boolean;
  watched_tech: boolean;
  min_cvss: number | null;
  outage_min_impact: "minor" | "major" | "critical";
  outage_providers: string[];
  bug_projects: string[];
  model_releases: boolean;
  model_providers: string[];
  briefing_ready: boolean;
}
