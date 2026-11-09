import { Cpu } from "lucide-react";
import type { Metadata } from "next";

import { FeedPage } from "@/components/feed/feed-page";

export const metadata: Metadata = { title: "AI Models" };

export default function Page() {
  return (
    <FeedPage
      title="AI Models"
      description="New model releases and versions, linked to the vendor's own announcement."
      icon={Cpu}
      types={["model_release"]}
      showSeverity={false}
      emptyTitle="No model releases collected yet"
      emptyDescription="No data sources are collecting this yet. Items appear here automatically once ingestion is enabled for matching sources."
    />
  );
}
