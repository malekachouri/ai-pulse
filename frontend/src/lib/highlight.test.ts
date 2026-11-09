import { describe, expect, it } from "vitest";

import { parseHighlights } from "@/lib/highlight";

describe("parseHighlights", () => {
  it("splits marked terms", () => {
    expect(parseHighlights("new [[RAG]] benchmark for [[retrieval]]")).toEqual([
      { text: "new ", match: false },
      { text: "RAG", match: true },
      { text: " benchmark for ", match: false },
      { text: "retrieval", match: true },
    ]);
  });

  it("treats HTML as plain text and tolerates unmatched markers", () => {
    expect(parseHighlights("<img src=x onerror=alert(1)> [[x")).toEqual([
      { text: "<img src=x onerror=alert(1)> [[x", match: false },
    ]);
  });
});
