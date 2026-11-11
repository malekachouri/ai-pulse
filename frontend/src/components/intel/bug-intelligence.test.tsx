import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BugIntelligenceFindings } from "@/components/intel/bug-intelligence";
import type { BugIntelligence, BugSection } from "@/lib/types";

const none: BugSection = { status: "insufficient", text: "insufficient information", text_is_ai: false, citations: [], facts: [] };

const intel: BugIntelligence = {
  subject: { kind: "vulnerability", id: "CVE-2026-41111", title: "Path traversal", article_id: "a", url: "https://nvd.nist.gov/vuln/detail/CVE-2026-41111" },
  status: "ready",
  sections: {
    cause: { status: "documented", text: "The upload handler does not normalise paths.", text_is_ai: true, citations: [1, 2], facts: [{ text: "Weakness: CWE-22", citation: 2 }] },
    impact: { status: "documented", text: null, text_is_ai: false, citations: [], facts: [{ text: "CVSS 9.8 (critical)", citation: 2 }] },
    affected_versions: none,
    fixes: { status: "documented", text: null, text_is_ai: false, citations: [], facts: [{ text: "Mentioned in the release notes of acme/widget v2.4.1", citation: 3 }] },
  },
  sources: [
    { n: 1, kind: "cve_record", title: "CVE-2026-41111: path traversal", url: "https://nvd.nist.gov/vuln/detail/CVE-2026-41111", published_at: null },
    { n: 2, kind: "cve_record", title: "CVE-2026-41111 record", url: "https://nvd.nist.gov/vuln/detail/CVE-2026-41111", published_at: null },
    { n: 3, kind: "release_notes", title: "acme/widget v2.4.1", url: "https://github.com/acme/widget/releases/tag/v2.4.1", published_at: null },
  ],
  unsupported_claims_removed: ["9.9.9"],
  ai_generated: true,
  provider: "fake",
  model: "m",
  generated_at: "2026-11-11T10:00:00Z",
  llm_available: true,
};

describe("BugIntelligenceFindings", () => {
  it("cites every fact and AI sentence, and says when the sources are silent", () => {
    render(
      <dl>
        <BugIntelligenceFindings d={intel} />
      </dl>,
    );
    expect(screen.getByText("Weakness: CWE-22")).toBeTruthy();
    expect(screen.getByText(/does not normalise paths/)).toBeTruthy();
    expect(screen.getByLabelText("AI-generated")).toBeTruthy();
    expect(screen.getByText(/Insufficient information in the collected sources/)).toBeTruthy();
    const notes = screen.getAllByRole("link", { name: "Source 3: acme/widget v2.4.1" });
    expect(notes[0]?.getAttribute("href")).toBe("https://github.com/acme/widget/releases/tag/v2.4.1");
    expect(screen.getAllByRole("link", { name: /^Source 2:/ })).toHaveLength(3); // cause fact, cause text, impact fact
    expect(screen.getByText("Release notes:")).toBeTruthy();
  });
});
