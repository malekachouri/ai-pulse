import { devices, expect, test, type Page } from "@playwright/test";

import { ACCOUNTS, login, open, watch } from "./helpers";

/**
 * The user journeys checked in the phase-9 audit, as regression tests. One fresh account per run.
 * Password reset reads the real email from the Mailpit test inbox (MAILPIT_URL), so SMTP delivery and the
 * reset link are covered end to end.
 */
const MAILPIT = process.env.MAILPIT_URL ?? "http://localhost:8025";
const email = `e2e-flow-${Date.now()}@example.com`;
const pw1 = "Correct-Horse-9-battery";
const pw2 = "Brand-New-Pass-77";

test.describe.configure({ mode: "serial" });

let page: Page;
let problems: string[];
let signedIn = false; // signed out, the app's silent refresh check answering 401 is expected

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage({ viewport: { width: 1280, height: 860 } });
  problems = watch(page, () => (signedIn ? "user" : "anon"));
});
test.afterAll(async () => page.close());

test("register: validation, then a valid account signs in", async () => {
  await open(page, "/register");
  await page.fill("#email", email);
  await page.fill("#password", pw1);
  await page.fill("#confirm", `${pw1}x`);
  await page.click("button[type=submit]");
  await expect(page.getByText("Passwords don't match.")).toBeVisible();
  await expect(page).toHaveURL(/\/register/);

  await page.fill("#name", "Flow Tester");
  await page.fill("#confirm", pw1);
  await Promise.all([page.waitForURL((u) => !u.pathname.startsWith("/register")), page.click("button[type=submit]")]);
  signedIn = true;
});

test("register: an existing email is refused", async ({ browser }) => {
  const other = await browser.newPage();
  await other.goto("/register");
  await other.fill("#email", email);
  await other.fill("#password", pw1);
  await other.fill("#confirm", pw1);
  await other.click("button[type=submit]");
  await expect(other.getByText("An account with this email already exists")).toBeVisible();
  await other.close();
});

test("session survives a full reload (refresh cookie)", async () => {
  await open(page, "/bookmarks");
  await expect(page.getByText("Sign in to see your bookmarks")).toHaveCount(0);
  await expect(page.getByRole("heading", { level: 1, name: "Bookmarks" })).toBeVisible();
});

test("feed: bookmark and read toggles, bookmarks page lists the item", async () => {
  await open(page, "/news");
  const first = page.locator("article").first();
  const title = (await first.locator("h2").innerText()).trim();
  await first.getByRole("button", { name: "Bookmark" }).click();
  await expect(first.getByRole("button", { name: "Remove bookmark" })).toBeVisible();
  await first.getByRole("button", { name: "Mark as read" }).click();
  await expect(first.getByRole("button", { name: "Mark as unread" })).toBeVisible();
  await open(page, "/bookmarks");
  await expect(page.getByText(title.slice(0, 40))).toBeVisible();
});

test("feed: search updates the URL and the results", async () => {
  await open(page, "/news");
  await page.getByLabel("Search this feed").fill("multimodal");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/q=multimodal/);
  await expect(page.locator("article h2").first()).toContainText(/multimodal/i);
});

test("search and Ask AI Pulse", async () => {
  await open(page, "/search");
  await page.getByLabel("Search query").fill("kubernetes");
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Search results").getByText(/kubernetes/i).first()).toBeVisible();
  const question = page.getByLabel("Question");
  await question.fill("Were there any outages today?");
  await question.press("Enter");
  // CI runs without an LLM: the answer explains that and lists the collected sources instead.
  await expect(page.getByText(/not enabled|no LLM provider/i).first()).toBeVisible({ timeout: 20_000 });
});

test("settings: a followed technology persists", async () => {
  await open(page, "/settings");
  await page.fill("#tech", "kubernetes");
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: /Save preferences/ }).click();
  await expect(page.getByText("Preferences saved")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("button", { name: "Remove kubernetes" }).first()).toBeVisible();
});

test("notifications: tabs switch and are reflected in the URL", async () => {
  await open(page, "/notifications");
  const tabs = page.getByRole("tab");
  expect(await tabs.count()).toBeGreaterThan(1);
  await tabs.nth(1).click();
  await expect(page).toHaveURL(/tab=/);
});

test("keyboard: the first Tab stop is 'Skip to content'", async () => {
  await open(page, "/news");
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toHaveText(/skip to content/i);
});

test("sign out ends the session", async () => {
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  signedIn = false;
  await expect(page.getByRole("link", { name: "Sign in" }).first()).toBeVisible();
  await open(page, "/bookmarks");
  await expect(page.getByText("Sign in to see your bookmarks")).toBeVisible();
});

test("login: a wrong password is refused", async () => {
  await open(page, "/login");
  await page.fill("#email", email);
  await page.fill("#password", "Wrong-Password-1");
  const before = problems.length;
  await page.click("button[type=submit]");
  await expect(page.getByText("Invalid email or password")).toBeVisible();
  expect(problems.slice(before)).toEqual(["api: POST /api/v1/auth/login -> 401"]); // the refusal itself
  problems.splice(before);
});

test("password reset by email, then sign in with the new password", async ({ request }) => {
  await open(page, "/forgot-password");
  await page.fill("#email", email);
  await page.click("button[type=submit]");
  await expect(page.getByText(/If an account exists/i)).toBeVisible();

  let link: string | undefined;
  await expect
    .poll(
      async () => {
        const list = await (await request.get(`${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:"${email}"`)}`)).json();
        const id = list.messages?.[0]?.ID;
        if (!id) return undefined;
        const msg = await (await request.get(`${MAILPIT}/api/v1/message/${id}`)).json();
        link = /https?:\/\/\S+\/reset-password\?token=\S+/.exec(msg.Text ?? "")?.[0];
        return link;
      },
      { timeout: 30_000, message: "reset email with a link" },
    )
    .toBeTruthy();

  await page.goto(new URL(link!).pathname + new URL(link!).search);
  await page.fill("#password", pw2);
  await page.fill("#confirm", pw2);
  await page.click("button[type=submit]");
  await expect(page.getByText("Password updated — please sign in")).toBeVisible();
  await login(page, email, pw2);
  signedIn = true;
  await expect(page).not.toHaveURL(/\/login/);
});

test("admin: change a user's role and change it back", async ({ browser }) => {
  const admin = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await login(admin, ACCOUNTS.admin.email, ACCOUNTS.admin.password);
  const adminProblems = watch(admin, "admin"); // after sign-in: the signed-out refresh check is expected
  await open(admin, "/admin/users");
  await admin.getByPlaceholder("Email or name").fill(email);
  const select = admin.getByLabel(`Role of ${email}`);
  await select.selectOption("analyst");
  await expect(admin.getByText(`Updated ${email}`).first()).toBeVisible();
  await expect(select).toHaveValue("analyst");
  await select.selectOption("user");
  await expect(select).toHaveValue("user");
  expect(adminProblems).toEqual([]);
  await admin.close();
});

test("learn: recommendations explain themselves; lessons need an LLM", async ({ browser }) => {
  const reader = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await login(reader, ACCOUNTS.user.email, ACCOUNTS.user.password);
  await open(reader, "/learn");
  await expect(reader.getByRole("heading", { level: 1, name: "Learn" })).toBeVisible();
  await expect(reader.getByText("Because you follow Kubernetes").first()).toBeVisible();
  // CI runs without an LLM: the page says so instead of showing invented lessons.
  await expect(reader.getByText("AI lessons are not enabled")).toBeVisible();
  const doc = reader.getByRole("link", { name: /Kubernetes documentation/ });
  await expect(doc).toHaveAttribute("href", "https://kubernetes.io/docs/home/");
  await reader.close();
});

test("release analysis shows what changed, citing both releases", async ({ browser }) => {
  const p = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await open(p, "/tools");
  const card = p.locator("article", { hasText: "example-org/e2e-agent-kit v1.1" }).first();
  await card.getByRole("button", { name: "Explain this item" }).click();
  const section = p.getByRole("region", { name: /what changed since v1\.0/i });
  await expect(section).toBeVisible();
  await expect(section.getByText("[E2E] Removed the old planner")).toBeVisible();
  await expect(section.getByText("+2.5")).toBeVisible();
  const cites = await section.getByRole("link", { name: /source: (this|previous) release/i }).evaluateAll((els) =>
    [...new Set(els.map((e) => e.getAttribute("href")))].sort(),
  );
  expect(cites).toEqual(["https://example.com/e2e/release-1.0", "https://example.com/e2e/release-1.1"]);
  await p.close();
});

test("watchlist: what the reader follows, with original sources", async ({ browser }) => {
  const reader = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await login(reader, ACCOUNTS.user.email, ACCOUNTS.user.password);
  await open(reader, "/watchlist");
  const entry = reader.getByRole("region", { name: "Kubernetes" });
  await expect(entry).toBeVisible();
  const link = entry.getByRole("link", { name: "[E2E] Kubernetes release adds a new scheduler feature" }).first();
  await expect(link).toHaveAttribute("href", "https://example.com/e2e/devops-1");
  await reader.close();
});

test("compare models: only cited numbers, 'not reported' otherwise", async ({ browser }) => {
  const p = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await open(p, "/models/compare");
  await p.getByRole("button", { name: /Example-7B/ }).click();
  await p.getByRole("button", { name: /Sample-13B/ }).click();
  await expect(p).toHaveURL(/ids=.*ids=/);
  const table = p.getByRole("region", { name: "Model comparison table" });
  const mmlu = table.getByRole("row", { name: /^MMLU/ });
  await expect(mmlu.getByText("64.2", { exact: true })).toBeVisible();
  await expect(mmlu.getByText("68.9", { exact: true })).toBeVisible();
  await expect(mmlu.getByRole("link", { name: /Source of MMLU for Example-7B/ })).toHaveAttribute("href", "https://example.com/e2e/model-1");
  const humaneval = table.getByRole("row", { name: /^HumanEval/ });
  await expect(humaneval.getByText("not reported")).toBeVisible(); // Sample-13B's source does not say
  await p.close();
});

test("bug intelligence on the CVE table: cited facts, insufficient information otherwise", async ({ browser }) => {
  const p = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await open(p, "/bugs?tab=vulnerabilities");
  await p.getByRole("button", { name: "Bug intelligence: CVE-2099-0101" }).click();
  const panel = p.getByRole("region", { name: "Bug intelligence" });
  await expect(panel).toBeVisible();
  await expect(panel.getByText(/^CVSS 9\.8 \(critical\)/)).toBeVisible();
  await expect(panel.getByText("Insufficient information in the collected sources.").first()).toBeVisible();
  await expect(panel.getByText("Facts only: AI explanations need an LLM provider.")).toBeVisible();
  await p.close();
});

test("weekly report: build last week's and download the PDF", async ({ browser }) => {
  const reader = await browser.newPage({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
  await login(reader, ACCOUNTS.user.email, ACCOUNTS.user.password);
  await open(reader, "/briefing");
  await reader.getByRole("button", { name: "Build last week's report" }).click();
  const button = reader.getByRole("button", { name: /Download the weekly report of .* as PDF/ }).first();
  await expect(button).toBeVisible();
  const [download] = await Promise.all([reader.waitForEvent("download"), button.click()]);
  expect(download.suggestedFilename()).toMatch(/^ai-pulse-weekly-\d{4}-\d{2}-\d{2}\.pdf$/);
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const c of stream) chunks.push(c as Buffer);
  expect(Buffer.concat(chunks).subarray(0, 8).toString()).toBe("%PDF-1.4");
  await reader.close();
});

test("mobile: the navigation drawer opens and navigates", async ({ browser }) => {
  const ctx = await browser.newContext({ ...devices["Pixel 7"] });
  const m = await ctx.newPage();
  await m.goto("/news");
  await m.getByRole("button", { name: "Open navigation" }).click();
  await m.getByRole("link", { name: /Security/ }).first().click();
  await expect(m).toHaveURL(/\/security/);
  await ctx.close();
});

test("no unexpected errors during the flows", async () => {
  expect(problems).toEqual([]);
});
