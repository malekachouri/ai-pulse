import { Cloud } from "lucide-react";
import type { Metadata } from "next";

import { FeedPage } from "@/components/feed/feed-page";

export const metadata: Metadata = { title: "DevOps & Cloud" };

export default function Page() {
  return (
    <FeedPage
      title="DevOps & Cloud"
      description="Kubernetes, Docker and cloud provider releases, announcements and incidents."
      icon={Cloud}
      types={["devops", "incident"]}
      showSeverity={true}
      emptyTitle="No DevOps or cloud updates collected yet"
      emptyDescription="No data sources are collecting this yet. Items appear here automatically once ingestion is enabled for matching sources."
    />
  );
}
