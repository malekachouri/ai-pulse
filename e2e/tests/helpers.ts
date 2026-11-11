import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, type TestInfo } from "@playwright/test";

export const ACCOUNTS = {
  admin: { email: process.env.E2E_ADMIN_EMAIL ?? "e2e-admin@example.com", password: process.env.E2E_ADMIN_PASSWORD ?? "" },
  user: { email: "e2e-reader@example.com", password: "E2e-Reader-Pass-2026" },
};
export type Role = "anon" | "user" | "admin";

export const ROUTES = [
  "/", "/news", "/models", "/tools", "/research", "/github", "/bugs", "/security", "/devops", "/analytics",
  "/search", "/briefing", "/bookmarks", "/notifications", "/settings",
  "/admin", "/admin/ai", "/admin/audit", "/admin/ingestion", "/admin/jobs", "/admin/sources", "/admin/users",
  "/login", "/register", "/forgot-password", "/reset-password",
];

/** API answers that are part of normal operation, not failures. */
function expected(method: string, path: string, status: number, role: Role): boolean {
  if (role === "anon" && method === "POST" && path === "/api/v1/auth/refresh" && status === 401) return true; // silent refresh, signed out
  if (method === "GET" && path === "/api/v1/briefings/latest" && status === 404) return true; // no briefing yet
  return false;
}

/** Records page errors, console errors (CSP violations, React errors) and unexpected API failures. */
export function watch(page: Page, role: Role | (() => Role)) {
  const current = typeof role === "function" ? role : () => role;
  const problems: string[] = [];
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    if (m.type() === "error" && !m.text().startsWith("Failed to load resource")) problems.push(`console: ${m.text().slice(0, 200)}`);
  });
  page.on("response", (r) => {
    const u = new URL(r.url());
    if (u.pathname.startsWith("/api/") && r.status() >= 400 && !expected(r.request().method(), u.pathname, r.status(), current()))
      problems.push(`api: ${r.request().method()} ${u.pathname}${u.search} -> ${r.status()}`);
  });
  return problems;
}

export async function useTheme(page: Page, testInfo: TestInfo): Promise<void> {
  const theme = (testInfo.project.metadata as { theme?: string }).theme ?? "dark";
  await page.addInitScript((t) => {
    try {
      localStorage.setItem("theme", t);
    } catch {
      /* storage unavailable: default theme */
    }
  }, theme);
}

export async function login(page: Page, email: string, password: string): Promise<void> {
  await page.goto("/login");
  await page.fill("#email", email);
  await page.fill("#password", password);
  await Promise.all([page.waitForURL((u) => !u.pathname.startsWith("/login")), page.click("button[type=submit]")]);
}

/** Navigates and waits until loading skeletons are gone. */
export async function open(page: Page, route: string): Promise<void> {
  await page.goto(route, { waitUntil: "load" });
  await page.waitForTimeout(500);
  await page
    .waitForFunction(() => !document.querySelector("[aria-busy=true], .animate-pulse"), null, { timeout: 15_000 })
    .catch(() => {});
}

export async function expectAccessible(page: Page, label: string): Promise<void> {
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"]).analyze();
  const found = r.violations.map((v) => `${v.id} (${v.impact}, ${v.nodes.length}): ${v.nodes[0]?.target.join(" ")}`);
  expect(found, `axe violations on ${label}`).toEqual([]);
}
