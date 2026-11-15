import { describe, expect, it } from "vitest";

import { demoFetch } from "@/lib/demo";
import type { Article, DashboardSummary, Page, Skill } from "@/lib/types";

describe("demo data", () => {
  it("is always visibly fictional", async () => {
    const page = await demoFetch<Page<Article>>("/news", "GET", { page_size: 100 });
    expect(page.items.length).toBeGreaterThan(10);
    for (const a of page.items) {
      expect(a.title.startsWith("[DEMO]")).toBe(true);
      expect(new URL(a.url).hostname).toBe("example.com");
      expect(a.source.name.startsWith("Demo source")).toBe(true);
      if (a.severity) expect(a.severity_basis).toMatch(/Demo/);
    }
  });

  it("labels radar entries as fictional", async () => {
    const skills = await demoFetch<Page<Skill>>("/skills", "GET");
    expect(skills.items.length).toBeGreaterThan(0);
    for (const s of skills.items) {
      expect(s.title?.startsWith("[DEMO]")).toBe(true);
      expect(new URL(s.listing_url).hostname).toBe("example.com");
    }
  });

  it("filters like the API", async () => {
    const vulns = await demoFetch<Page<Article>>("/news", "GET", { item_type: ["vulnerability"], severity: ["critical"] });
    expect(vulns.items.every((a) => a.item_type === "vulnerability" && a.severity === "critical")).toBe(true);
    const summary = await demoFetch<DashboardSummary>("/dashboard/summary", "GET");
    expect(summary.activity_14d).toHaveLength(14);
  });
});
