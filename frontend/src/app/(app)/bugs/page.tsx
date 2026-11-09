"use client";

import { Bug } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { RadarOverview } from "@/components/radar/overview";
import { BugsTable, IncidentsTable, VulnsTable } from "@/components/radar/tables";
import { ListSkeleton } from "@/components/states/states";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const TABS = ["overview", "bugs", "incidents", "vulnerabilities"] as const;

function Radar() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const raw = params.get("tab");
  const tab = (TABS as readonly string[]).includes(raw ?? "") ? (raw as string) : "overview";
  return (
    <Tabs value={tab} onValueChange={(v) => router.replace(v === "overview" ? pathname : `${pathname}?tab=${v}`, { scroll: false })}>
      <TabsList className="mb-4 flex h-auto flex-wrap justify-start">
        <TabsTrigger value="overview">Overview</TabsTrigger>
        <TabsTrigger value="bugs">Bugs</TabsTrigger>
        <TabsTrigger value="incidents">Incidents</TabsTrigger>
        <TabsTrigger value="vulnerabilities">Vulnerabilities</TabsTrigger>
      </TabsList>
      <TabsContent value="overview"><RadarOverview /></TabsContent>
      <TabsContent value="bugs"><BugsTable /></TabsContent>
      <TabsContent value="incidents"><IncidentsTable /></TabsContent>
      <TabsContent value="vulnerabilities"><VulnsTable /></TabsContent>
    </Tabs>
  );
}

export default function BugsRadarPage() {
  return (
    <>
      <PageHeader
        title="Bugs & Failures Radar"
        description="Public bugs, provider incidents and vulnerabilities from official sources. Severity is only shown with its documented basis; an incident is active only when the provider's own status was verified in the last 2 hours."
        icon={Bug}
      />
      <Suspense fallback={<ListSkeleton />}>
        <Radar />
      </Suspense>
    </>
  );
}
