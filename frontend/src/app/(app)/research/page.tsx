import { FileText } from "lucide-react";
import type { Metadata } from "next";

import { FeedPage } from "@/components/feed/feed-page";

export const metadata: Metadata = { title: "Research Papers" };

export default function Page() {
  return (
    <FeedPage
      title="Research Papers"
      description="Recent papers from arXiv and other research sources."
      icon={FileText}
      types={["research"]}
      showSeverity={false}
      emptyTitle="No papers collected yet"
      emptyDescription="No data sources are collecting this yet. Items appear here automatically once ingestion is enabled for matching sources."
    />
  );
}
