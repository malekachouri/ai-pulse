import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReleaseChanges } from "@/components/intel/release-changes";
import type { ReleaseChanges as Changes } from "@/lib/types";

const CUR = "https://github.com/example-org/infer/releases/tag/v1.3.0";
const PREV = "https://github.com/example-org/infer/releases/tag/v1.2.0";

const base: Changes = {
  current: { article_id: "a", title: "example-org/infer v1.3.0", url: CUR, version: "v1.3.0", published_at: null },
  previous: { article_id: "b", title: "example-org/infer v1.2.0", url: PREV, version: "v1.2.0", published_at: null },
  version_change: { from: "v1.2.0", to: "v1.3.0", bump: "minor" },
  license: { status: "changed", current: { value: "MIT", basis: "licensed under the MIT License" }, previous: { value: "Apache-2.0", basis: "x" } },
  benchmarks: [
    { name: "MMLU", current: 73.5, previous: 71.2, delta: 2.3, status: "changed", quotes: { current: "MMLU: 73.5", previous: "MMLU 71.2" } },
    { name: "HumanEval", current: 81, previous: "not documented", delta: null, status: "only in current", quotes: { current: "HumanEval 81.0%", previous: null } },
  ],
  benchmarks_status: "documented",
  changelog: { status: "documented", source: "current", sections: [{ heading: "Breaking changes", kind: "breaking", items: ["Removed the legacy flag"] }] },
  citations: { current: CUR, previous: PREV },
  method: "Rule-based comparison of the two source texts. Nothing is generated or inferred.",
};

describe("ReleaseChanges", () => {
  it("cites both sources and shows the comparison", () => {
    render(<ReleaseChanges c={base} />);
    expect(screen.getByRole("heading", { name: /what changed since v1\.2\.0/i })).toBeTruthy();
    expect(screen.getByText("+2.3")).toBeTruthy();
    expect(screen.getByText("Removed the legacy flag")).toBeTruthy();
    const sources = screen.getAllByRole("link", { name: /source: (this|previous) release/i });
    expect(new Set(sources.map((a) => a.getAttribute("href")))).toEqual(new Set([CUR, PREV]));
    expect(screen.getAllByText("not documented").length).toBe(1); // HumanEval had no previous score
  });

  it("says 'not documented' instead of inventing anything", () => {
    render(
      <ReleaseChanges
        c={{
          ...base,
          license: { status: "not documented", current: { value: "not documented", basis: null }, previous: { value: "not documented", basis: null } },
          benchmarks: [],
          benchmarks_status: "not documented",
          changelog: { status: "not documented", source: "current", sections: [] },
        }}
      />,
    );
    expect(screen.getByText(/not documented in either release/i)).toBeTruthy();
    expect(screen.getByText(/not documented in the release notes/i)).toBeTruthy();
    expect(screen.getAllByText("not documented").length).toBe(2);
  });
});
