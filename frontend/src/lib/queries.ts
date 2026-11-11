"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, buildQuery, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  AdminSource,
  AdminUser,
  AIConfig,
  AuditLogEntry,
  CollectionJob,
  ConnectorInfo,
  RoleInfo,
  SystemHealth,
  UsageStats,
  AIModel,
  AIStatus,
  BugIntelligence,
  ModelComparison,
  Watchlist,
  WeeklyReportItem,
  Article,
  ArticleAnalysis,
  AskResponse,
  ArticleFilters,
  Bookmark,
  Briefing,
  BriefingListItem,
  Category,
  DashboardSummary,
  GitHubRepository,
  Incident,
  IngestionOverview,
  Lessons,
  FollowType,
  Notification,
  NotificationKind,
  Page,
  Preferences,
  Recommendations,
  RadarIncident,
  RadarSummary,
  SoftwareBug,
  Vulnerability,
  SearchCapabilities,
  SearchResponse,
  SecurityStats,
  SourceBrief,
  UnreadCount,
} from "@/lib/types";

export const keys = {
  dashboard: ["dashboard"] as const,
  news: (f: ArticleFilters) => ["news", f] as const,
  categories: ["categories"] as const,
  sources: ["sources"] as const,
  bookmarks: (page: number) => ["bookmarks", page] as const,
  notifications: ["notifications"] as const,
  unread: ["notifications", "unread"] as const,
  preferences: ["preferences"] as const,
  briefingLatest: ["briefings", "latest"] as const,
  briefingByDate: (d: string) => ["briefings", "date", d] as const,
  briefings: ["briefings"] as const,
};

export function useDashboard() {
  return useQuery({ queryKey: keys.dashboard, queryFn: () => api.get<DashboardSummary>("/dashboard/summary") });
}

export function useNews(filters: ArticleFilters) {
  return useQuery({
    queryKey: keys.news(filters),
    queryFn: () => api.get<Page<Article>>("/news", { ...filters }),
    placeholderData: keepPreviousData,
  });
}

export function useCategories() {
  return useQuery({ queryKey: keys.categories, queryFn: () => api.get<Category[]>("/categories"), staleTime: 3_600_000 });
}

export function useSources() {
  return useQuery({ queryKey: keys.sources, queryFn: () => api.get<SourceBrief[]>("/sources"), staleTime: 600_000 });
}

export function useBookmarks(page: number) {
  const { status } = useAuth();
  return useQuery({
    queryKey: keys.bookmarks(page),
    queryFn: () => api.get<Page<Bookmark>>("/bookmarks", { page, page_size: 20 }),
    enabled: status === "authenticated",
    placeholderData: keepPreviousData,
  });
}

/** Optimistically flips a boolean flag on every cached copy of an article. */
function patchArticleCaches(qc: ReturnType<typeof useQueryClient>, id: string, patch: Partial<Article>) {
  const fix = (a: Article) => (a.id === id ? { ...a, ...patch } : a);
  qc.setQueriesData<Page<Article>>({ queryKey: ["news"] }, (old) => (old ? { ...old, items: old.items.map(fix) } : old));
  qc.setQueryData<DashboardSummary>(keys.dashboard, (old) =>
    old
      ? {
          ...old,
          latest: old.latest.map(fix),
          latest_ai: old.latest_ai.map(fix),
          top_security: old.top_security.map(fix),
          recent_failures: old.recent_failures.map(fix),
        }
      : old,
  );
}

export function useToggleBookmark() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, on }: { id: string; on: boolean }) =>
      on ? api.put(`/bookmarks/${id}`) : api.delete(`/bookmarks/${id}`),
    onMutate: ({ id, on }) => patchArticleCaches(qc, id, { is_bookmarked: on }),
    onError: (err, { id, on }) => {
      patchArticleCaches(qc, id, { is_bookmarked: !on });
      toast.error(errorMessage(err));
    },
    onSuccess: (_d, { on }) => toast.success(on ? "Saved to bookmarks" : "Removed from bookmarks"),
    onSettled: () => qc.invalidateQueries({ queryKey: ["bookmarks"] }),
  });
}

export function useToggleRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, read }: { id: string; read: boolean }) =>
      read ? api.put(`/news/${id}/read`) : api.delete(`/news/${id}/read`),
    onMutate: ({ id, read }) => patchArticleCaches(qc, id, { is_read: read }),
    onError: (err, { id, read }) => {
      patchArticleCaches(qc, id, { is_read: !read });
      toast.error(errorMessage(err));
    },
  });
}

export function useUnreadCount() {
  const { status } = useAuth();
  return useQuery({
    queryKey: keys.unread,
    queryFn: () => api.get<UnreadCount>("/notifications/unread-count"),
    enabled: status === "authenticated",
    refetchInterval: 60_000,
  });
}

export function useNotifications(enabled: boolean) {
  const { status } = useAuth();
  return useQuery({
    queryKey: keys.notifications,
    queryFn: () => api.get<Page<Notification>>("/notifications", { page_size: 15 }),
    enabled: enabled && status === "authenticated",
  });
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string | "all") =>
      id === "all" ? api.post("/notifications/read-all") : api.post(`/notifications/${id}/read`),
    onSettled: () => qc.invalidateQueries({ queryKey: keys.notifications }),
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export interface NotificationQuery {
  kind?: NotificationKind[];
  unread_only?: boolean;
  page: number;
  page_size?: number;
}

export function useNotificationList(q: NotificationQuery) {
  const { status } = useAuth();
  return useQuery({
    queryKey: [...keys.notifications, "list", q],
    queryFn: () => api.get<Page<Notification>>("/notifications", { page_size: 20, ...q, unread_only: q.unread_only || undefined }),
    enabled: status === "authenticated",
    placeholderData: keepPreviousData,
  });
}

type NotificationAction =
  | { type: "read" | "unread" | "delete"; id: string }
  | { type: "read-all"; kind?: NotificationKind[] };

export function useNotificationAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (a: NotificationAction) => {
      if (a.type === "read-all") return api.post(`/notifications/read-all${buildQuery({ kind: a.kind })}`);
      if (a.type === "delete") return api.delete(`/notifications/${a.id}`);
      return api.post(`/notifications/${a.id}/${a.type}`);
    },
    onSuccess: (_d, a) => {
      if (a.type === "delete") toast.success("Notification deleted");
    },
    onSettled: () => qc.invalidateQueries({ queryKey: keys.notifications }),
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export function useFollow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ type, value, follow }: { type: FollowType; value: string; follow: boolean }) =>
      api.post<Preferences>(`/preferences/${follow ? "follow" : "unfollow"}`, { type, value }),
    onSuccess: (data, v) => {
      qc.setQueryData(keys.preferences, data);
      toast.success(v.follow ? `Following ${v.value}` : `Unfollowed ${v.value}`);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export function usePreferences() {
  const { status } = useAuth();
  return useQuery({
    queryKey: keys.preferences,
    queryFn: () => api.get<Preferences>("/preferences"),
    enabled: status === "authenticated",
  });
}

export function useUpdatePreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: Partial<Preferences>) => api.put<Preferences>("/preferences", p),
    onSuccess: (data) => {
      qc.setQueryData(keys.preferences, data);
      toast.success("Preferences saved");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

/** Briefings depend on who is signed in (personalised vs general), so wait for the session and key by user. */
function useViewer() {
  const { status, user } = useAuth();
  return { ready: status !== "loading", viewer: user?.id ?? "anonymous" };
}

export function useLatestBriefing() {
  const { ready, viewer } = useViewer();
  return useQuery({
    queryKey: [...keys.briefingLatest, viewer],
    enabled: ready,
    queryFn: async () => {
      try {
        return await api.get<Briefing>("/briefings/latest");
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null; // none generated yet
        throw err;
      }
    },
  });
}

export function useBriefingByDate(date: string | null) {
  const { ready, viewer } = useViewer();
  return useQuery({
    queryKey: [...keys.briefingByDate(date ?? ""), viewer],
    queryFn: () => api.get<Briefing>(`/briefings/${date}`),
    enabled: ready && Boolean(date),
  });
}

export function useBriefings() {
  const { ready, viewer } = useViewer();
  return useQuery({
    queryKey: [...keys.briefings, "list", viewer],
    queryFn: () => api.get<BriefingListItem[]>("/briefings"),
    enabled: ready,
  });
}

// ---- Typed intelligence modules ----

export function useIncidents(params: { active_only?: boolean; page_size?: number; sort?: string }) {
  return useQuery({
    queryKey: ["incidents", params],
    queryFn: () => api.get<Page<Incident>>("/incidents", params),
    refetchInterval: 120_000,
  });
}

export function useSecurityStats() {
  return useQuery({ queryKey: ["security", "stats"], queryFn: () => api.get<SecurityStats>("/security/stats") });
}

export function useRisingRepos() {
  return useQuery({
    queryKey: ["github", "rising"],
    queryFn: () => api.get<Page<GitHubRepository>>("/github/repositories", { sort: "-stars_delta_7d", page_size: 6 }),
  });
}

export function useModels() {
  return useQuery({
    queryKey: ["models", "recent"],
    queryFn: () => api.get<Page<AIModel>>("/models", { sort: "-updated_at", page_size: 6 }),
  });
}

export function useSearch(params: { q: string; item_type?: string[]; page: number; mode?: string }) {
  return useQuery({
    queryKey: ["search", params],
    queryFn: () => api.get<SearchResponse>("/search", { ...params, page_size: 20 }),
    enabled: params.q.trim().length >= 2,
    placeholderData: keepPreviousData,
  });
}

// ---- Ingestion admin ----
export function useIngestionStatus(enabled: boolean) {
  return useQuery({
    queryKey: ["admin", "ingestion"],
    queryFn: () => api.get<IngestionOverview>("/admin/ingestion/status"),
    enabled,
    refetchInterval: 30_000,
  });
}

export function useIngestionActions() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["admin", "ingestion"] });
  const run = useMutation({
    mutationFn: (sourceId: string) => api.post<{ task_id: string }>(`/admin/sources/${sourceId}/run`),
    onSuccess: () => {
      toast.success("Run queued — results appear here within a minute");
      setTimeout(refresh, 4000);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
  const retry = useMutation({
    mutationFn: (jobId: string) => api.post<{ task_id: string }>(`/admin/jobs/${jobId}/retry`),
    onSuccess: () => {
      toast.success("Retry queued");
      setTimeout(refresh, 4000);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
  const update = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: { enabled?: boolean; poll_interval_minutes?: number } }) =>
      api.patch(`/admin/sources/${id}`, patch),
    onSuccess: () => {
      toast.success("Source updated");
      refresh();
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
  return { run, retry, update };
}


// ---- AI engine ----
export function useArticleAnalysis(id: string | null) {
  return useQuery({
    queryKey: ["analysis", id],
    queryFn: () => api.get<ArticleAnalysis>(`/news/${id}/analysis`),
    enabled: !!id,
  });
}

export function useSearchCapabilities() {
  return useQuery({ queryKey: ["search", "caps"], queryFn: () => api.get<SearchCapabilities>("/search/capabilities"), staleTime: 300_000 });
}

export function useAsk() {
  return useMutation({
    mutationFn: (question: string) => api.post<AskResponse>("/search/ask", { question }),
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export function useRecommendations() {
  const { status } = useAuth();
  return useQuery({
    queryKey: ["learning", "recommendations"],
    queryFn: () => api.get<Recommendations>("/learning/recommendations"),
    enabled: status === "authenticated",
  });
}

export function useLessons() {
  const { status } = useAuth();
  return useQuery({
    queryKey: ["learning", "lessons"],
    queryFn: () => api.get<Lessons>("/learning/lessons"),
    enabled: status === "authenticated",
  });
}

export function useGenerateLessons() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<Lessons>("/learning/lessons/generate"),
    onSuccess: (data) => {
      qc.setQueryData(["learning", "lessons"], data);
      toast.success(data.lessons.length ? "Lessons ready" : "No important items to learn from yet today");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export function useGenerateBriefing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<Briefing>("/briefings/generate"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.briefings });
      toast.success("Briefing generated");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export function useAIStatus(enabled: boolean) {
  return useQuery({ queryKey: ["admin", "ai"], queryFn: () => api.get<AIStatus>("/admin/ai/status"), enabled, refetchInterval: 60_000 });
}


// ---- Bugs & Failures Radar ----
type Params = Record<string, string | number | boolean | string[] | undefined>;

export function useRadar(days = 30) {
  return useQuery({ queryKey: ["radar", days], queryFn: () => api.get<RadarSummary>("/radar/summary", { days }), refetchInterval: 120_000 });
}

export function useBugList(params: Params) {
  return useQuery({ queryKey: ["bugs", params], queryFn: () => api.get<Page<SoftwareBug>>("/bugs", params), placeholderData: keepPreviousData });
}

export function useIncidentList(params: Params) {
  return useQuery({ queryKey: ["incidents", "list", params], queryFn: () => api.get<Page<RadarIncident>>("/incidents", params), placeholderData: keepPreviousData });
}

export function useVulnList(params: Params) {
  return useQuery({ queryKey: ["vulns", params], queryFn: () => api.get<Page<Vulnerability>>("/security/vulnerabilities", params), placeholderData: keepPreviousData });
}

// ---- Administration ----

type AdminParams = Record<string, string | number | boolean | string[] | undefined>;

export function useSystemHealth(enabled: boolean) {
  return useQuery({
    queryKey: ["admin", "system"],
    queryFn: () => api.get<SystemHealth>("/admin/system/health"),
    enabled,
    refetchInterval: 30_000,
  });
}

export function useUsageStats(enabled: boolean, days: number) {
  return useQuery({
    queryKey: ["admin", "usage", days],
    queryFn: () => api.get<UsageStats>("/admin/usage", { days }),
    enabled,
  });
}

export function useAIConfig(enabled: boolean) {
  return useQuery({ queryKey: ["admin", "ai-config"], queryFn: () => api.get<AIConfig>("/admin/ai/config"), enabled });
}

export function useAdminUsers(params: AdminParams, enabled: boolean) {
  return useQuery({
    queryKey: ["admin", "users", params],
    queryFn: () => api.get<Page<AdminUser>>("/admin/users", params),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function useRoles(enabled: boolean) {
  return useQuery({ queryKey: ["admin", "roles"], queryFn: () => api.get<RoleInfo[]>("/admin/roles"), enabled });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...patch }: { id: string; role?: string; is_active?: boolean }) =>
      api.patch<AdminUser>(`/admin/users/${id}`, patch),
    onSuccess: (u) => {
      toast.success(`Updated ${u.email}`);
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
      qc.invalidateQueries({ queryKey: ["admin", "roles"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export function useJobs(params: AdminParams, enabled: boolean) {
  return useQuery({
    queryKey: ["admin", "jobs", params],
    queryFn: () => api.get<Page<CollectionJob>>("/admin/jobs", params),
    enabled,
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });
}

export function useRetryFailedJobs() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (hours: number) =>
      api.post<{ retried: number; skipped_sources: string[] }>(`/admin/jobs/retry-failed${buildQuery({ hours })}`),
    onSuccess: (r) => {
      toast.success(r.retried ? `${r.retried} source(s) queued for retry` : "Nothing to retry");
      qc.invalidateQueries({ queryKey: ["admin"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export function useAuditLogs(params: AdminParams, enabled: boolean) {
  return useQuery({
    queryKey: ["admin", "audit", params],
    queryFn: () => api.get<Page<AuditLogEntry>>("/admin/audit-logs", params),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function useAdminSources(enabled: boolean) {
  return useQuery({ queryKey: ["admin", "sources"], queryFn: () => api.get<AdminSource[]>("/admin/sources"), enabled });
}

export function useConnectors(enabled: boolean) {
  return useQuery({ queryKey: ["admin", "connectors"], queryFn: () => api.get<ConnectorInfo[]>("/admin/connectors"), enabled, staleTime: Infinity });
}

export function useSourceMutations() {
  const qc = useQueryClient();
  const done = () => qc.invalidateQueries({ queryKey: ["admin"] });
  return {
    create: useMutation({
      mutationFn: (body: Record<string, unknown>) => api.post<AdminSource>("/admin/sources", body),
      onSuccess: (s) => {
        toast.success(`Source ${s.slug} created`);
        done();
      },
      onError: (err) => toast.error(errorMessage(err)),
    }),
    update: useMutation({
      mutationFn: ({ id, ...patch }: { id: string } & Record<string, unknown>) => api.patch<AdminSource>(`/admin/sources/${id}`, patch),
      onSuccess: (s) => {
        toast.success(`Source ${s.slug} saved`);
        done();
      },
      onError: (err) => toast.error(errorMessage(err)),
    }),
    remove: useMutation({
      mutationFn: (id: string) => api.delete(`/admin/sources/${id}`),
      onSuccess: () => {
        toast.success("Source deleted");
        done();
      },
      onError: (err) => toast.error(errorMessage(err)),
    }),
  };
}

export function useWatchlist() {
  const { status } = useAuth();
  return useQuery({
    queryKey: ["watchlist"],
    queryFn: () => api.get<Watchlist>("/watchlist"),
    enabled: status === "authenticated",
  });
}

export function useBugIntelligence(articleId: string | null) {
  return useQuery({
    queryKey: ["bug-intelligence", articleId],
    queryFn: () => api.get<BugIntelligence>(`/news/${articleId}/bug-intelligence`),
    enabled: !!articleId,
  });
}

export function useGenerateBugIntelligence(articleId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<BugIntelligence>(`/news/${articleId}/bug-intelligence`),
    onSuccess: (data) => {
      qc.setQueryData(["bug-intelligence", articleId], data);
      toast.success("Explanation ready");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}

export function useModelPicker(q: string) {
  return useQuery({
    queryKey: ["models", "picker", q],
    queryFn: () => api.get<Page<AIModel>>("/models", { q: q || undefined, sort: "-updated_at", page_size: 30 }),
    placeholderData: keepPreviousData,
  });
}

export function useModelComparison(ids: string[]) {
  return useQuery({
    queryKey: ["models", "compare", ids],
    queryFn: () => api.get<ModelComparison>("/models/compare", { ids }),
    enabled: ids.length >= 2,
  });
}

export function useWeeklyReports() {
  const { status } = useAuth();
  return useQuery({
    queryKey: ["briefings", "weekly"],
    queryFn: () => api.get<WeeklyReportItem[]>("/briefings/weekly"),
    enabled: status === "authenticated",
  });
}

export function useGenerateWeeklyReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<WeeklyReportItem>("/briefings/weekly/generate"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["briefings", "weekly"] });
      toast.success("Weekly report ready");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
}
