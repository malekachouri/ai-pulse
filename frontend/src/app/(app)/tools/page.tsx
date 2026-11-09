import { Wrench } from "lucide-react";
import type { Metadata } from "next";

import { FeedPage } from "@/components/feed/feed-page";

export const metadata: Metadata = { title: "AI Tools" };

export default function Page() {
  return (
    <FeedPage
      title="AI Tools"
      description="Frameworks, libraries and platforms for building AI systems."
      icon={Wrench}
      types={["tool"]}
      showSeverity={false}
      emptyTitle="No AI tools collected yet"
      emptyDescription="No data sources are collecting this yet. Items appear here automatically once ingestion is enabled for matching sources."
    />
  );
}
