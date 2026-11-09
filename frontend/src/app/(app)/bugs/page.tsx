import { Bug } from "lucide-react";
import type { Metadata } from "next";

import { FeedPage } from "@/components/feed/feed-page";
import { ActiveIncidentsPanel } from "@/components/intel/panels";

export const metadata: Metadata = { title: "Bugs & Failures" };

export default function Page() {
  return (
    <FeedPage
      panel={<ActiveIncidentsPanel />}
      title="Bugs & Failures"
      description="Public bug reports, regressions and service incidents. Incident status always comes from the provider's own status page."
      icon={Bug}
      types={["bug", "incident"]}
      showSeverity={true}
      emptyTitle="No bugs or incidents collected yet"
      emptyDescription="No data sources are collecting this yet. Items appear here automatically once ingestion is enabled for matching sources."
    />
  );
}
