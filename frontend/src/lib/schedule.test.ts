import { describe, expect, it } from "vitest";

import { scheduleSummary } from "@/lib/schedule";

describe("scheduleSummary", () => {
  const base = { briefing_hour: 7, briefing_weekday: 0, timezone: "Europe/Paris" } as const;
  it("describes each frequency", () => {
    expect(scheduleSummary({ ...base, briefing_frequency: "daily" })).toContain("every day at 07:00 (Europe/Paris)");
    expect(scheduleSummary({ ...base, briefing_frequency: "weekdays" })).toContain("Monday to Friday");
    expect(scheduleSummary({ ...base, briefing_frequency: "weekly", briefing_weekday: 4 })).toContain("every Friday");
    expect(scheduleSummary({ ...base, briefing_frequency: "off" })).toMatch(/on demand/);
  });
});
