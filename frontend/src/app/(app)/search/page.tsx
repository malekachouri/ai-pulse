import { Search } from "lucide-react";
import type { Metadata } from "next";
import { Suspense } from "react";

import { AskPanel } from "@/components/feed/ask-panel";
import { SearchView } from "@/components/feed/search-view";
import { PageHeader } from "@/components/layout/page-header";
import { ListSkeleton } from "@/components/states/states";

export const metadata: Metadata = { title: "Search" };

export default function Page() {
  return (
    <>
      <PageHeader
        title="Search"
        description="Ask a question answered only from collected items (with citations), or search by keyword, meaning (semantic) or both (hybrid)."
        icon={Search}
      />
      <AskPanel />
      <Suspense fallback={<ListSkeleton />}>
        <SearchView />
      </Suspense>
    </>
  );
}
