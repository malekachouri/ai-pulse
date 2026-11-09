import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ArticleCard } from "@/components/feed/article-card";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { Article } from "@/lib/types";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ status: "anonymous", user: null }) }));

const base: Article = {
  id: "1",
  item_type: "vulnerability",
  title: "CVE-2026-0001 in libexample",
  description: "Heap overflow in parser.",
  url: "https://nvd.nist.gov/vuln/detail/CVE-2026-0001",
  author: null,
  published_at: "2026-11-08T10:00:00Z",
  collected_at: "2026-11-08T10:30:00Z",
  verification_status: "official",
  severity: "critical",
  severity_basis: "NVD CVSS v3.1 base score 9.8",
  importance_score: 93.4,
  tags: [],
  source: { id: "s", slug: "nvd", name: "NVD", source_type: "api", is_official: true, reliability: 0.95 },
  categories: [{ id: 1, slug: "cybersecurity", name: "Cybersecurity" }],
  duplicate_of_id: null,
  is_bookmarked: false,
  is_read: false,
  ai_summary: null,
};

function renderCard(a: Article) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <TooltipProvider>
        <ArticleCard article={a} />
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

describe("ArticleCard", () => {
  it("shows source, provenance, severity label and the original link", () => {
    renderCard(base);
    expect(screen.getByText("NVD")).toBeInTheDocument();
    expect(screen.getByText("Official source")).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(screen.getByText("Cybersecurity")).toBeInTheDocument();
    expect(screen.getByLabelText("Importance 93 of 100")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: base.title })).toHaveAttribute("href", base.url);
    expect(screen.getByRole("link", { name: /Source/ })).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.queryByText(/AI-generated/)).not.toBeInTheDocument();
  });

  it("labels AI summaries as AI-generated", () => {
    renderCard({ ...base, ai_summary: { short: "Patch now.", provider: "openai", model: "m", generated_at: base.collected_at } });
    expect(screen.getByText(/AI-generated summary/)).toBeInTheDocument();
    expect(screen.getByText("Patch now.")).toBeInTheDocument();
  });

  it("never renders unsafe URLs as links", () => {
    renderCard({ ...base, url: "javascript:alert(1)" });
    expect(screen.queryByRole("link", { name: base.title })).not.toBeInTheDocument();
    expect(screen.getByText(base.title)).toBeInTheDocument();
  });

  it("states when an item has no importance score", () => {
    renderCard({ ...base, importance_score: null, severity: null });
    expect(screen.getByText("Not scored")).toBeInTheDocument();
  });
});
