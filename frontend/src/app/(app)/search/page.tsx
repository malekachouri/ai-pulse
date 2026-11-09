import { Search } from "lucide-react";
import type { Metadata } from "next";
import { Suspense } from "react";

import { SearchView } from "@/components/feed/search-view";
import { PageHeader } from "@/components/layout/page-header";
import { ListSkeleton } from "@/components/states/states";

export const metadata: Metadata = { title: "Search" };

export default function Page() {
  return (
    <>
      <PageHeader
        title="Search"
        description="Keyword search across every collected item, ranked by relevance. Semantic search and Q&A with citations arrive with the AI engine."
        icon={Search}
      />
      <Suspense fallback={<ListSkeleton />}>
        <SearchView />
      </Suspense>
    </>
  );
}
