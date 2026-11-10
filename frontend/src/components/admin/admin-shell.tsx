"use client";

import { ShieldAlert } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { EmptyState, ListSkeleton, SignInRequired } from "@/components/states/states";
import { useAuth } from "@/lib/auth";
import type { HealthStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

export const ADMIN_TABS: { href: string; label: string; adminOnly?: boolean }[] = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/users", label: "Users & roles", adminOnly: true },
  { href: "/admin/sources", label: "Sources", adminOnly: true },
  { href: "/admin/ingestion", label: "Connector health" },
  { href: "/admin/jobs", label: "Jobs & failures" },
  { href: "/admin/ai", label: "AI providers & usage" },
  { href: "/admin/audit", label: "Audit log", adminOnly: true },
];

export function AdminNav() {
  const pathname = usePathname();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  return (
    <nav aria-label="Administration" className="-mx-1 mb-5 flex gap-1 overflow-x-auto border-b pb-px">
      {ADMIN_TABS.filter((t) => isAdmin || !t.adminOnly).map((t) => {
        const active = t.href === "/admin" ? pathname === "/admin" : pathname.startsWith(t.href);
        return (
          <Link
            key={t.href}
            href={t.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "shrink-0 rounded-t-md border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              active ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}

/** Renders children only for staff (admin, analyst) — or admins only — with clear states otherwise. */
export function StaffGate({ adminOnly, what, children }: { adminOnly?: boolean; what: string; children: React.ReactNode }) {
  const { user, status } = useAuth();
  if (status === "loading") return <ListSkeleton rows={3} />;
  if (status !== "authenticated" || !user) return <SignInRequired what={what} />;
  const allowed = adminOnly ? user.role === "admin" : user.role === "admin" || user.role === "analyst";
  if (!allowed)
    return (
      <EmptyState
        icon={ShieldAlert}
        title={adminOnly ? "Administrators only" : "Administrators and analysts only"}
        description="Ask an administrator for access. The API enforces the same rule."
      />
    );
  return <>{children}</>;
}

export function useIsStaff() {
  const { user } = useAuth();
  return { staff: user?.role === "admin" || user?.role === "analyst", admin: user?.role === "admin" };
}

const TONE: Record<HealthStatus, string> = {
  ok: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  degraded: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  down: "border-sev-critical/40 bg-sev-critical/10 text-sev-critical",
};

export function HealthPill({ status, className }: { status: HealthStatus; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-semibold uppercase", TONE[status], className)}>
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {status}
    </span>
  );
}
