"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatDay } from "@/lib/utils";

const axis = { stroke: "var(--chart-axis)", fontSize: 11, tickLine: false, axisLine: false } as const;

function TooltipBox({ label, value, unit }: { label: string; value: number; unit: string }) {
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-xs shadow-lg">
      <p className="text-muted-foreground">{label}</p>
      <p className="tabular mt-0.5 font-semibold text-foreground">
        {value.toLocaleString("en")} {unit}
      </p>
    </div>
  );
}

/** Single-series time series: 2px line, light fill, crosshair tooltip. */
export function ActivityChart({ data, height = 220 }: { data: { day: string; count: number }[]; height?: number }) {
  return (
    <div style={{ height }} role="img" aria-label="Items collected per day over the last 14 days">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="activityFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-series)" stopOpacity={0.28} />
              <stop offset="100%" stopColor="var(--chart-series)" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis dataKey="day" tickFormatter={formatDay} {...axis} minTickGap={24} />
          <YAxis allowDecimals={false} {...axis} width={44} tickFormatter={(v: number) => v.toLocaleString("en")} />
          <Tooltip
            cursor={{ stroke: "var(--chart-axis)", strokeDasharray: "3 3" }}
            content={({ active, payload, label }) =>
              active && payload?.[0] ? (
                <TooltipBox label={formatDay(String(label))} value={Number(payload[0].value)} unit="items" />
              ) : null
            }
          />
          <Area
            type="monotone"
            dataKey="count"
            stroke="var(--chart-series)"
            strokeWidth={2}
            fill="url(#activityFill)"
            activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--card)" }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Horizontal magnitude bars, one hue, value labels at the bar end. */
export function DistributionChart({
  data,
  unit = "items",
  colors,
}: {
  data: { label: string; count: number }[];
  unit?: string;
  /** Optional per-bar colours — only for reserved status colours (severity). */
  colors?: string[];
}) {
  const height = Math.max(120, data.length * 34 + 16);
  return (
    <div style={{ height }} role="img" aria-label={`Distribution: ${data.map((d) => `${d.label} ${d.count}`).join(", ")}`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 40, bottom: 0, left: 0 }} barCategoryGap={6}>
          <XAxis type="number" hide allowDecimals={false} />
          <YAxis type="category" dataKey="label" width={130} {...axis} tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} />
          <Tooltip
            cursor={{ fill: "var(--muted)", opacity: 0.5 }}
            content={({ active, payload }) =>
              active && payload?.[0] ? (
                <TooltipBox label={String(payload[0].payload.label)} value={Number(payload[0].value)} unit={unit} />
              ) : null
            }
          />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={20} isAnimationActive={false}>
            {data.map((d, i) => (
              <Cell key={d.label} fill={colors?.[i] ?? "var(--chart-series)"} />
            ))}
            <LabelList dataKey="count" position="right" className="tabular" fill="var(--muted-foreground)" fontSize={11} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
