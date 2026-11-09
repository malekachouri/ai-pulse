"use client";

import { ErrorState } from "@/components/states/states";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return <ErrorState error={error} onRetry={reset} className="mt-10" />;
}
