import type { LucideIcon } from "lucide-react";
import { Suspense } from "react";

import { FeedView, type FeedViewProps } from "@/components/feed/feed-view";
import { PageHeader } from "@/components/layout/page-header";
import { ListSkeleton } from "@/components/states/states";

export function FeedPage({
  title,
  description,
  icon,
  panel,
  ...feed
}: FeedViewProps & { title: string; description: string; icon: LucideIcon; panel?: React.ReactNode }) {
  return (
    <>
      <PageHeader title={title} description={description} icon={icon} />
      {panel}
      <Suspense fallback={<ListSkeleton />}>
        <FeedView {...feed} />
      </Suspense>
    </>
  );
}
