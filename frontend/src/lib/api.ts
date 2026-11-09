/**
 * Typed API client. Requests go to the same origin (/api/v1, proxied to FastAPI by Next.js).
 * The access token lives only in memory; the refresh token is an httpOnly cookie the browser
 * sends to /api/v1/auth/* automatically. A 401 triggers one silent refresh + retry.
 */
import { demoFetch, isDemoMode } from "@/lib/demo";

export const API_BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let accessToken: string | null = null;
let refreshInFlight: Promise<string | null> | null = null;
const listeners = new Set<(token: string | null) => void>();

export function getAccessToken() {
  return accessToken;
}

export function setAccessToken(token: string | null) {
  accessToken = token;
  listeners.forEach((l) => l(token));
}

export function onAccessTokenChange(listener: (token: string | null) => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export async function refreshAccessToken(): Promise<string | null> {
  if (isDemoMode()) {
    setAccessToken("demo");
    return "demo";
  }
  refreshInFlight ??= (async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, { method: "POST", credentials: "same-origin" });
      if (!res.ok) {
        setAccessToken(null);
        return null;
      }
      const data = (await res.json()) as { access_token: string };
      setAccessToken(data.access_token);
      return data.access_token;
    } catch {
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

type Query = Record<string, string | number | boolean | string[] | undefined | null>;

export function buildQuery(params?: Query): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => sp.append(key, v));
    else sp.set(key, String(value));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as { error?: { code: string; message: string; details?: unknown } };
    if (body.error) return new ApiError(res.status, body.error.code, body.error.message, body.error.details);
  } catch {
    /* non-JSON body (e.g. proxy error) */
  }
  if (res.status >= 500 || res.status === 0) {
    return new ApiError(res.status, "unavailable", "The AI Pulse API is unreachable or returned an error.");
  }
  return new ApiError(res.status, "http_error", res.statusText || "Request failed");
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit & { query?: Query; auth?: boolean } = {},
): Promise<T> {
  const { query, auth = true, ...rest } = init;
  const url = `${API_BASE}${path}${buildQuery(query)}`;
  if (isDemoMode()) return demoFetch<T>(path, rest.method ?? "GET", query, rest.body);

  const doFetch = (token: string | null) => {
    const headers = new Headers(rest.headers);
    if (rest.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    if (auth && token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(url, { ...rest, headers, credentials: "same-origin" });
  };

  let res: Response;
  try {
    res = await doFetch(accessToken);
  } catch {
    throw new ApiError(0, "network_error", "Network error: could not reach the AI Pulse API.");
  }
  if (res.status === 401 && auth && accessToken && !path.startsWith("/auth/")) {
    const fresh = await refreshAccessToken();
    if (fresh) res = await doFetch(fresh);
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string, query?: Query) => apiFetch<T>(path, { query }),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: "PUT", body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
};

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === "validation_error" && Array.isArray(err.details) && err.details[0]) {
      const first = err.details[0] as { msg?: string };
      return first.msg?.replace(/^Value error, /, "") ?? err.message;
    }
    return err.message;
  }
  return err instanceof Error ? err.message : "Something went wrong";
}
