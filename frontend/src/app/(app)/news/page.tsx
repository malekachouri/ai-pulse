import { Newspaper } from "lucide-react";
import type { Metadata } from "next";

import { FeedPage } from "@/components/feed/feed-page";

export const metadata: Metadata = { title: "AI News" };

export default function Page() {
  return (
    <FeedPage
      title="AI News"
      description="Announcements and news from official AI vendor and research channels."
      icon={Newspaper}
      types={["news"]}
      showSeverity={false}
      emptyTitle="No AI news collected yet"
      emptyDescription="No data sources are collecting this yet. Items appear here automatically once ingestion is enabled for matching sources."
    />
  );
}
