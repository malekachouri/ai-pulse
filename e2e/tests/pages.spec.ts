import { expect, test } from "@playwright/test";

import { ACCOUNTS, expectAccessible, login, open, ROUTES, useTheme, watch, type Role } from "./helpers";

/**
 * Every page, for every role: renders an h1, no JavaScript or CSP error, no unexpected API failure,
 * no horizontal scrolling, and no axe-core violation (WCAG 2.0/2.1 A and AA, plus best practices).
 */
for (const role of ["anon", "user", "admin"] as Role[]) {
  test(`${role}: every page renders cleanly and passes axe-core`, async ({ page }, testInfo) => {
    await useTheme(page, testInfo);
    const problems = watch(page, role);
    if (role !== "anon") await login(page, ACCOUNTS[role].email, ACCOUNTS[role].password);

    for (const route of ROUTES) {
      await test.step(route, async () => {
        const before = problems.length;
        await open(page, route);
        await expect(page.locator("h1").first(), `h1 on ${route}`).toBeVisible();
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        expect(overflow, `horizontal overflow on ${route}`).toBeLessThanOrEqual(1);
        await expectAccessible(page, `${route} (${role}, ${testInfo.project.name})`);
        expect(problems.slice(before), `errors on ${route}`).toEqual([]);
      });
    }
  });
}

test("access control: private and admin pages say so instead of showing data", async ({ page }) => {
  await open(page, "/bookmarks");
  await expect(page.getByText("Sign in to see your bookmarks")).toBeVisible();
  await login(page, ACCOUNTS.user.email, ACCOUNTS.user.password);
  await open(page, "/admin/users");
  await expect(page.getByText(/Administrators( and analysts)? only/).first()).toBeVisible();
});
