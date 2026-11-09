import { Search } from "lucide-react";
import type { Metadata } from "next";

import { FeedPage } from "@/components/feed/feed-page";

export const metadata: Metadata = { title: "Search" };

export default function Page() {
  return (
    <FeedPage
      title="Search"
      description="Keyword search across every collected item. Semantic search and Q&A with citations arrive with the AI engine."
      icon={Search}
      types={[]}
      showSeverity
      emptyTitle="Nothing collected yet"
      emptyDescription="No data sources are collecting this yet. Items appear here automatically once ingestion is enabled for matching sources."
    />
  );
}
