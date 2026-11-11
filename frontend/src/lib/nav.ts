import {
  GraduationCap,
  BarChart3,
  Bell,
  Bookmark,
  Boxes,
  Bug,
  Cloud,
  Cpu,
  DatabaseZap,
  Gauge,
  FileText,
  GitPullRequest,
  LayoutDashboard,
  Newspaper,
  Settings,
  ShieldAlert,
  Sunrise,
  Wrench,
  type LucideIcon,
} from "lucide-react";

import type { Role } from "@/lib/types";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  group: "Intelligence" | "Radar" | "You" | "Admin";
  /** Only shown to these roles. */
  roles?: Role[];
}

export const NAV: NavItem[] = [
  { href: "/", label: "Overview", icon: LayoutDashboard, group: "Intelligence" },
  { href: "/news", label: "AI News", icon: Newspaper, group: "Intelligence" },
  { href: "/models", label: "AI Models", icon: Cpu, group: "Intelligence" },
  { href: "/tools", label: "AI Tools", icon: Wrench, group: "Intelligence" },
  { href: "/research", label: "Research Papers", icon: FileText, group: "Intelligence" },
  { href: "/github", label: "GitHub Radar", icon: GitPullRequest, group: "Radar" },
  { href: "/bugs", label: "Bugs & Failures", icon: Bug, group: "Radar" },
  { href: "/security", label: "Security & CVEs", icon: ShieldAlert, group: "Radar" },
  { href: "/devops", label: "DevOps & Cloud", icon: Cloud, group: "Radar" },
  { href: "/briefing", label: "Daily Briefing", icon: Sunrise, group: "You" },
  { href: "/learn", label: "Learn", icon: GraduationCap, group: "You" },
  { href: "/notifications", label: "Notifications", icon: Bell, group: "You" },
  { href: "/bookmarks", label: "Bookmarks", icon: Bookmark, group: "You" },
  { href: "/analytics", label: "Analytics", icon: BarChart3, group: "You" },
  { href: "/settings", label: "Settings", icon: Settings, group: "You" },
  { href: "/admin", label: "Administration", icon: Gauge, group: "Admin", roles: ["admin", "analyst"] },
  { href: "/admin/ingestion", label: "Connector health", icon: DatabaseZap, group: "Admin", roles: ["admin", "analyst"] },
];

export const BrandIcon: LucideIcon = Boxes;
