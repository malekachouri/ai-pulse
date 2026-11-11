"use client";

import { ChartColumn, Table } from "lucide-react";
import { useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/** Card with a chart/table switch so every chart has an accessible data-table view. */
export function ChartCard({
  title,
  description,
  table,
  children,
  className,
}: {
  title: string;
  description?: string;
  table: { columns: [string, string]; rows: [string, number][] };
  children: React.ReactNode;
  className?: string;
}) {
  const [view, setView] = useState<"chart" | "table">("chart");
  return (
    <Card className={className}>
      <CardHeader>
        <div>
          <CardTitle>{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </div>
        <div className="flex rounded-md border p-0.5" role="group" aria-label={`${title} view`}>
          {(["chart", "table"] as const).map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={view === v}
              aria-label={v === "chart" ? "Chart view" : "Table view"}
              onClick={() => setView(v)}
              className={cn(
                "rounded px-1.5 py-1 text-muted-foreground",
                view === v && "bg-accent text-foreground",
              )}
            >
              {v === "chart" ? <ChartColumn className="size-3.5" /> : <Table className="size-3.5" />}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {view === "chart" ? (
          children
        ) : (
          <div className="max-h-64 overflow-y-auto rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring" tabIndex={0} role="region" aria-label={`${title} (data table)`}>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="py-1.5 font-medium">{table.columns[0]}</th>
                  <th className="py-1.5 text-right font-medium">{table.columns[1]}</th>
                </tr>
              </thead>
              <tbody>
                {table.rows.map(([k, v]) => (
                  <tr key={k} className="border-b last:border-0">
                    <td className="py-1.5">{k}</td>
                    <td className="tabular py-1.5 text-right">{v.toLocaleString("en")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
