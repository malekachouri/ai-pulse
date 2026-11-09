"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  AIModel,
  Article,
  ArticleFilters,
  Bookmark,
  Briefing,
  BriefingListItem,
  Category,
  DashboardSummary,
  GitHubRepository,
  Incident,
  Notification,
  Page,
  Preferences,
  SearchResponse,
  SecurityStats,
  SourceBrief,
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
    queryFn: () => api.get<{ unread: number }>("/notifications/unread-count"),
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

export function useLatestBriefing() {
  return useQuery({
    queryKey: keys.briefingLatest,
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

export function useBriefings() {
  return useQuery({ queryKey: keys.briefings, queryFn: () => api.get<BriefingListItem[]>("/briefings") });
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

export function useSearch(params: { q: string; item_type?: string[]; page: number }) {
  return useQuery({
    queryKey: ["search", params],
    queryFn: () => api.get<SearchResponse>("/search", { ...params, page_size: 20 }),
    enabled: params.q.trim().length >= 2,
    placeholderData: keepPreviousData,
  });
}
