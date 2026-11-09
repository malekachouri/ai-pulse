import { ShieldAlert } from "lucide-react";
import type { Metadata } from "next";

import { FeedPage } from "@/components/feed/feed-page";
import { SecurityStatsStrip } from "@/components/intel/panels";

export const metadata: Metadata = { title: "Security & CVEs" };

export default function Page() {
  return (
    <FeedPage
      panel={<SecurityStatsStrip />}
      title="Security & CVEs"
      description="Vulnerabilities from NVD, CISA KEV and vendor advisories. Severity is shown with its official basis."
      icon={ShieldAlert}
      types={["vulnerability"]}
      showSeverity={true}
      emptyTitle="No vulnerabilities collected yet"
      emptyDescription="No data sources are collecting this yet. Items appear here automatically once ingestion is enabled for matching sources."
    />
  );
}
