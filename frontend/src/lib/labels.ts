import type { ItemType, Severity, VerificationStatus } from "@/lib/types";

export const ITEM_TYPE_LABEL: Record<ItemType, string> = {
  news: "News",
  model_release: "Model release",
  tool: "Tool",
  research: "Research",
  github_repo: "Repository",
  github_issue: "GitHub issue",
  bug: "Bug",
  vulnerability: "Vulnerability",
  incident: "Incident",
  devops: "DevOps",
};

export const SEVERITIES: Severity[] = ["critical", "high", "medium", "low", "info"];

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
  unknown: "Unknown",
};

/** CSS variable per severity (reserved status colours; always shown with a text label). */
export const SEVERITY_COLOR: Record<Severity, string> = {
  critical: "var(--sev-critical)",
  high: "var(--sev-high)",
  medium: "var(--sev-medium)",
  low: "var(--sev-low)",
  info: "var(--sev-info)",
  unknown: "var(--sev-info)",
};

export const VERIFICATION_LABEL: Record<VerificationStatus, { label: string; hint: string }> = {
  official: { label: "Official source", hint: "Collected directly from the vendor's or authority's own channel." },
  verified: { label: "Verified", hint: "Cross-checked against an official source." },
  unverified: { label: "Unverified", hint: "Third-party report that has not been confirmed yet." },
  disputed: { label: "Disputed", hint: "Conflicting information exists; treat with caution." },
};

export const INTEREST_LABEL: Record<string, string> = {
  "ai-engineering": "AI Engineering",
  "generative-ai": "Generative AI",
  rag: "RAG",
  "ai-agents": "AI Agents",
  llmops: "LLMOps",
  devops: "DevOps",
  cloud: "Cloud",
  kubernetes: "Kubernetes",
  cybersecurity: "Cybersecurity",
  "software-engineering": "Software Engineering",
};
