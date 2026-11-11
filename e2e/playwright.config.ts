import { defineConfig, devices } from "@playwright/test";

/**
 * Browser end-to-end tests against a running stack (production build). Start it with ../scripts/e2e.sh,
 * which also seeds labelled test data and the accounts. E2E_BASE_URL defaults to http://localhost:3000.
 *
 * Projects: every page is checked on desktop (dark and light theme) and on a phone; the user flows run
 * once, on desktop. Tests run serially: the stack is shared and refresh tokens rotate on every use.
 */
export default defineConfig({
  testDir: "./tests",
  globalSetup: "./global-setup.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0, // a failure must be investigated, not retried away
  timeout: 300_000, // one test visits every page for one role
  globalTimeout: 25 * 60_000, // a hung browser fails the run instead of stalling CI
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "off",
    navigationTimeout: 30_000,
    actionTimeout: 15_000,
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } }, metadata: { theme: "dark" } },
    {
      name: "desktop-light",
      use: { viewport: { width: 1440, height: 900 } },
      metadata: { theme: "light" },
      testMatch: /pages\.spec\.ts/,
    },
    { name: "mobile", use: { ...devices["Pixel 7"] }, metadata: { theme: "dark" }, testMatch: /pages\.spec\.ts/ },
  ],
});
