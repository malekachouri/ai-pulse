"use client";

import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Tooltip } from "@/components/ui/tooltip";
import { useAuth } from "@/lib/auth";
import { BrandIcon, NAV, type NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

export function isActive(pathname: string, href: string) {
  return href === "/" || href === "/admin" ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
}

function Brand({ collapsed }: { collapsed: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2.5 px-1" aria-label="AI Pulse home">
      <span className="flex size-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-blue to-brand-violet text-white shadow-md shadow-brand-violet/30">
        <BrandIcon className="size-4.5" />
      </span>
      {!collapsed && (
        <span className="leading-tight">
          <span className="block text-sm font-semibold tracking-tight text-foreground">AI Pulse</span>
          <span className="block text-[11px] text-muted-foreground">Tech intelligence</span>
        </span>
      )}
    </Link>
  );
}

function NavLink({ item, collapsed, onNavigate }: { item: NavItem; collapsed: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();
  const active = isActive(pathname, item.href);
  const link = (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm transition-colors",
        active
          ? "bg-sidebar-active font-medium text-sidebar-active-foreground"
          : "text-sidebar-foreground hover:bg-accent/60 hover:text-foreground",
        collapsed && "justify-center px-0",
      )}
    >
      <item.icon className={cn("size-4.5 shrink-0", active && "text-primary dark:text-blue-300")} />
      {!collapsed && <span className="truncate">{item.label}</span>}
    </Link>
  );
  return collapsed ? (
    <Tooltip content={item.label} side="right">
      {link}
    </Tooltip>
  ) : (
    link
  );
}

export function SidebarNav({ collapsed = false, onNavigate }: { collapsed?: boolean; onNavigate?: () => void }) {
  const { user } = useAuth();
  const visible = NAV.filter((n) => !n.roles || (user && n.roles.includes(user.role)));
  const groups = (["Intelligence", "Radar", "You", "Admin"] as const).filter((g) => visible.some((n) => n.group === g));
  return (
    <nav aria-label="Main" className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
      {groups.map((g) => (
        <div key={g}>
          {!collapsed && (
            <p className="mb-1.5 px-2.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">{g}</p>
          )}
          <div className="space-y-0.5">
            {visible.filter((n) => n.group === g).map((item) => (
              <NavLink key={item.href} item={item} collapsed={collapsed} onNavigate={onNavigate} />
            ))}
          </div>
        </div>
      ))}
    </nav>
  );
}

export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  return (
    <aside
      className={cn(
        "sticky top-0 hidden h-dvh shrink-0 flex-col border-r bg-sidebar transition-[width] duration-200 lg:flex",
        collapsed ? "w-[68px]" : "w-60",
      )}
    >
      <div className={cn("flex h-16 items-center border-b px-4", collapsed && "justify-center px-0")}>
        <Brand collapsed={collapsed} />
      </div>
      <SidebarNav collapsed={collapsed} />
      <div className="border-t p-3">
        <button
          type="button"
          onClick={onToggle}
          className={cn(
            "flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-sm text-muted-foreground hover:bg-accent/60 hover:text-foreground",
            collapsed && "justify-center px-0",
          )}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
        >
          {collapsed ? <PanelLeftOpen className="size-4.5" /> : <PanelLeftClose className="size-4.5" />}
          {!collapsed && "Collapse"}
        </button>
      </div>
    </aside>
  );
}

export { Brand };
