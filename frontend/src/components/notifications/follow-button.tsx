"use client";

import { Check, Loader2, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { useFollow, usePreferences } from "@/lib/queries";
import type { FollowType, Preferences } from "@/lib/types";
import { cn } from "@/lib/utils";

const FIELD: Record<FollowType, keyof Pick<Preferences, "followed_technologies" | "followed_repositories" | "followed_providers">> = {
  technology: "followed_technologies",
  repository: "followed_repositories",
  provider: "followed_providers",
};

/** One-click follow / unfollow for a technology, an `owner/name` repository or an AI provider. */
export function FollowButton({ type, value, className }: { type: FollowType; value: string; className?: string }) {
  const { status } = useAuth();
  const prefs = usePreferences();
  const follow = useFollow();
  if (status !== "authenticated") return null;
  const list = prefs.data?.[FIELD[type]] ?? [];
  const following = list.some((v) => v.toLowerCase() === value.toLowerCase());
  const pending = follow.isPending && follow.variables?.value === value;
  return (
    <Button
      type="button"
      size="sm"
      variant={following ? "secondary" : "outline"}
      className={cn("h-7 gap-1 px-2 text-xs", className)}
      disabled={pending || prefs.isLoading}
      aria-pressed={following}
      aria-label={following ? `Unfollow ${value}` : `Follow ${value}`}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        follow.mutate({ type, value, follow: !following });
      }}
    >
      {pending ? <Loader2 className="size-3 animate-spin" /> : following ? <Check className="size-3" /> : <Plus className="size-3" />}
      {following ? "Following" : "Follow"}
    </Button>
  );
}
