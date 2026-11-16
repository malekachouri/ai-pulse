import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ExplanationView, SkillExplanationPanel } from "@/components/skills/skill-explanation";
import type { Skill, SkillExplanation } from "@/lib/types";

const d: SkillExplanation = {
  status: "ready",
  sections: {
    what_it_does: { text: "It runs read-only SQL against PostgreSQL.", insufficient: false, citations: [1, 2] },
    how_it_helps: { text: "AI Pulse stores its data in PostgreSQL, so Claude Code could inspect the tables.", insufficient: false, citations: [3, 1] },
    how_to_try: { text: "insufficient information", insufficient: true, citations: [] },
    cautions: { text: "Use a database role that cannot write.", insufficient: false, citations: [2] },
  },
  sources: [
    { n: 1, kind: "listing", title: "Official listing: pg-mcp", url: "https://registry.test/pg-mcp" },
    { n: 2, kind: "readme", title: "Project README", url: "https://github.com/acme/pg-mcp" },
    { n: 3, kind: "ai_pulse", title: "AI Pulse (this project)", url: null },
  ],
  unsupported_claims_removed: ["40%"],
  ai_generated: true,
  provider: "ollama",
  model: "qwen2.5:3b",
  generated_at: "2026-11-16T10:00:00Z",
  listing_version: "0.2.0",
  llm_available: true,
};

describe("ExplanationView", () => {
  it("labels the text as AI-generated, cites every section and says when the sources are silent", () => {
    render(<ExplanationView d={d} />);
    expect(screen.getByText("AI-generated")).toBeTruthy();
    expect(screen.getByText(/ollama · qwen2\.5:3b/)).toBeTruthy();
    expect(screen.getByText(/for version 0\.2\.0/)).toBeTruthy();
    expect(screen.getByText("How it could help AI Pulse")).toBeTruthy();
    expect(screen.getByText(/Claude Code could inspect the tables/)).toBeTruthy();
    expect(screen.getByText("Insufficient information in the sources.")).toBeTruthy();
    expect(screen.getAllByRole("link", { name: "Source 1: Official listing: pg-mcp" })[0]?.getAttribute("href")).toBe("https://registry.test/pg-mcp");
    expect(screen.getAllByRole("link", { name: /^Source 2:/ })).toHaveLength(2);
    expect(screen.queryByRole("link", { name: /^Source 3:/ })).toBeNull(); // AI Pulse itself: cited, no external link
    expect(screen.getByLabelText("Source 3: AI Pulse (this project)")).toBeTruthy();
    expect(screen.getByText(/removed here: 40%/)).toBeTruthy();
  });
});

describe("SkillExplanationPanel", () => {
  it("is hidden when there is no model and nothing stored", () => {
    const s = { id: "1", explained_at: null } as Skill;
    const { container } = render(<SkillExplanationPanel s={s} llmAvailable={false} />);
    expect(container.innerHTML).toBe("");
  });
});
