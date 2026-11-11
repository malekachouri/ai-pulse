"use client";

import { LogOut, Settings, User as UserIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";

function initials(name: string | null, email: string) {
  const src = name?.trim() || email;
  const parts = src.split(/[\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "U";
}

export function UserMenu() {
  const { user, status, logout } = useAuth();
  const router = useRouter();

  if (status === "loading") return <Skeleton className="size-8 rounded-full" />;
  if (!user)
    return (
      <Button asChild size="sm" variant="brand">
        <Link href="/login">Sign in</Link>
      </Button>
    );

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className="flex size-8 items-center justify-center rounded-full bg-gradient-to-br from-brand-blue to-brand-violet text-xs font-semibold text-white outline-none ring-offset-2 ring-offset-background focus-visible:ring-2 focus-visible:ring-ring"
          // Starts with the visible initials (WCAG 2.5.3, label in name): "ER, account menu".
          aria-label={`${initials(user.full_name, user.email)}, account menu`}
        >
          {initials(user.full_name, user.email)}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="text-foreground">
          <p className="truncate text-sm font-medium">{user.full_name || "Your account"}</p>
          <p className="truncate text-xs font-normal text-muted-foreground">{user.email}</p>
          <p className="mt-1 text-[11px] font-normal uppercase tracking-wide text-muted-foreground">{user.role}</p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/settings">
            <UserIcon /> Profile
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/settings#preferences">
            <Settings /> Preferences
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={async () => {
            await logout();
            router.push("/");
          }}
        >
          <LogOut /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
