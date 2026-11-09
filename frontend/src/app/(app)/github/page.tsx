import { GitPullRequest } from "lucide-react";
import type { Metadata } from "next";

import { FeedPage } from "@/components/feed/feed-page";

export const metadata: Metadata = { title: "GitHub Radar" };

export default function Page() {
  return (
    <FeedPage
      title="GitHub Radar"
      description="Fast-rising repositories (ranked by stars gained between our own snapshots — GitHub has no trending API) and notable issues."
      icon={GitPullRequest}
      types={["github_repo", "github_issue"]}
      showSeverity={false}
      emptyTitle="No GitHub activity collected yet"
      emptyDescription="No data sources are collecting this yet. Items appear here automatically once ingestion is enabled for matching sources."
    />
  );
}
