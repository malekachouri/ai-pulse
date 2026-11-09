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

export interface Notification {
  id: string;
  kind: string;
  severity: Severity;
  title: string;
  body: string | null;
  article_id: string | null;
  link: string | null;
  created_at: string;
  read_at: string | null;
}

export type BriefingFrequency = "daily" | "weekdays" | "weekly" | "off";

export interface Preferences {
  interests: string[];
  followed_technologies: string[];
  followed_repositories: string[];
  followed_providers: string[];
  min_notification_severity: Severity;
  briefing_frequency: BriefingFrequency;
  briefing_hour: number;
  timezone: string;
  theme: string;
}

export interface BriefingSectionItem {
  article_id?: string;
  title: string;
  url?: string;
  summary?: string;
}

export interface Briefing {
  id: string;
  user_id: string | null;
  briefing_date: string;
  period_start: string;
  period_end: string;
  executive_summary: string | null;
  sections: Record<string, BriefingSectionItem[] | string>;
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
