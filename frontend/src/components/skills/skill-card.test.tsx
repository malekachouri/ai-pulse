import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { seenLine, SkillCard } from "@/components/skills/skill-card";
import type { Skill } from "@/lib/types";

const base: Skill = {
  id: "1",
  kind: "mcp_server",
  name: "io.github.acme/postgres-mcp",
  title: "Postgres MCP",
  description: "Query PostgreSQL databases from an AI assistant.",
  version: "0.1.10",
  publisher: "io.github.acme",
  category: null,
  status: "active",
  source: { slug: "mcp-registry", name: "Official MCP Registry" },
  listing_url: "https://registry.modelcontextprotocol.io/v0/servers/io.github.acme%2Fpostgres-mcp/versions/latest",
  homepage_url: "javascript:alert(1)",
  repository_url: "https://github.com/acme/postgres-mcp",
  install: [
    {
      label: "Run locally from npm",
      command: "claude mcp add postgres-mcp -e 'DATABASE_URL=<DATABASE_URL>' -- npx -y postgres-mcp@0.1.10",
      notes: ["Set DATABASE_URL (secret): Connection string"],
    },
    { label: "cargo package postgres-mcp", command: null, notes: ["No standard runner for 'cargo' packages: follow the listing."] },
  ],
  stack_tags: ["postgresql", "docker"],
  published_at: "2026-11-14T10:27:16Z",
  source_updated_at: null,
  first_seen_at: new Date().toISOString(),
  initial: false,
  is_new: true,
  explained_at: null,
};

describe("SkillCard", () => {
  it("shows the listing facts, the technologies and copyable install commands", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<SkillCard s={base} />);

    expect(screen.getByRole("heading", { name: "Postgres MCP" })).toBeTruthy();
    expect(screen.getByText("MCP server")).toBeTruthy();
    expect(screen.getByText("v0.1.10")).toBeTruthy();
    expect(screen.getByText("New")).toBeTruthy();
    expect(screen.getByText("PostgreSQL")).toBeTruthy();
    expect(screen.getByText("Docker")).toBeTruthy();
    expect(screen.getByText(/by io\.github\.acme/)).toBeTruthy();

    expect(screen.getByText(/npx -y postgres-mcp@0\.1\.10/)).toBeTruthy();
    expect(screen.getByText("Set DATABASE_URL (secret): Connection string")).toBeTruthy();
    expect(screen.getByText(/No standard runner for 'cargo'/)).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /^Copy:/ })).toHaveLength(1); // no command, no copy button
    fireEvent.click(screen.getByRole("button", { name: "Copy: Run locally from npm" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(base.install[0]?.command));

    expect(screen.getByRole("link", { name: /Official listing/ }).getAttribute("href")).toBe(base.listing_url);
    expect(screen.getByRole("link", { name: /Source code/ }).getAttribute("href")).toBe("https://github.com/acme/postgres-mcp");
    expect(screen.queryByRole("link", { name: /Website/ })).toBeNull(); // unsafe URL is not linked
  });

  it("marks inactive and baseline entries", () => {
    render(<SkillCard s={{ ...base, status: "deprecated", initial: true, is_new: false, stack_tags: [], install: [] }} />);
    expect(screen.getByText("deprecated")).toBeTruthy();
    expect(screen.queryByText("New")).toBeNull();
    expect(screen.queryByText(/Technologies:/)).toBeNull();
    expect(screen.queryByText(/How to install/)).toBeNull();
    expect(screen.getByText(/Listed before AI Pulse started watching this source/)).toBeTruthy();
  });
});

describe("seenLine", () => {
  it("states the listing's date and when AI Pulse first saw the entry", () => {
    const line = seenLine({ kind: "plugin", published_at: null, first_seen_at: new Date().toISOString(), initial: false });
    expect(line.startsWith("First seen")).toBe(true);
    expect(seenLine({ kind: "mcp_server", published_at: "2026-11-14T10:27:16Z", first_seen_at: "2026-11-15T00:00:00Z", initial: false })).toMatch(/^Version published .* · First seen/);
  });
});
