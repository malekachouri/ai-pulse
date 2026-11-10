"use client";

import { Cpu, KeyRound } from "lucide-react";
import { useState } from "react";

import { HealthPill, StaffGate, useIsStaff } from "@/components/admin/admin-shell";
import { ActivityChart } from "@/components/charts/charts";
import { ChartCard } from "@/components/charts/chart-card";
import { PageHeader } from "@/components/layout/page-header";
import { Td, Th } from "@/components/radar/shared";
import { ErrorState, ListSkeleton } from "@/components/states/states";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/native-select";
import { useAIConfig, useAIStatus, useUsageStats } from "@/lib/queries";
import { formatDay } from "@/lib/utils";

function Row({ k, v, env }: { k: string; v: React.ReactNode; env: string }) {
  return (
    <div className="grid grid-cols-[1fr_auto] gap-3 border-b py-1.5 text-sm last:border-0">
      <dt>
        {k}
        <code className="ml-2 text-[11px] text-muted-foreground">{env}</code>
      </dt>
      <dd className="tabular text-right font-medium">{v ?? <span className="text-muted-foreground">not set</span>}</dd>
    </div>
  );
}

function AIAdmin() {
  const { staff } = useIsStaff();
  const [days, setDays] = useState(30);
  const cfg = useAIConfig(staff);
  const status = useAIStatus(staff);
  const usage = useUsageStats(staff, days);
  const c = cfg.data;
  const s = status.data;
  const u = usage.data;
  const money = (n: number | null | undefined) => (n == null ? "—" : `$${n.toFixed(4)}`);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div>
              <CardTitle className="flex items-center gap-2">
                <KeyRound className="size-4 text-primary" /> Provider configuration
              </CardTitle>
              <CardDescription>
                Read-only by design: providers and keys are set with environment variables (or your secret manager) and the
                services restarted. Keys never pass through the API, the database or the browser.
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            {cfg.isLoading ? (
              <ListSkeleton rows={2} />
            ) : cfg.isError ? (
              <ErrorState error={cfg.error} onRetry={() => cfg.refetch()} />
            ) : c ? (
              <dl>
                <Row k="LLM provider" env="LLM_PROVIDER" v={c.llm_provider} />
                <Row k="LLM model" env="LLM_MODEL" v={c.llm_model} />
                <Row k="Embedding provider" env="EMBEDDING_PROVIDER" v={c.embedding_provider} />
                <Row k="Embedding model" env="EMBEDDING_MODEL" v={c.embedding_model} />
                <Row k="Embedding dimensions" env="EMBEDDING_DIM" v={c.embedding_dim} />
                <Row k="OpenAI key" env="OPENAI_API_KEY" v={c.openai_api_key_set ? "configured" : null} />
                <Row k="Anthropic key" env="ANTHROPIC_API_KEY" v={c.anthropic_api_key_set ? "configured" : null} />
                <Row k="OpenAI-compatible URL" env="OPENAI_BASE_URL" v={c.openai_base_url} />
                <Row k="Ollama URL" env="OLLAMA_BASE_URL" v={c.ollama_base_url} />
                <Row k="Timeout" env="LLM_TIMEOUT_SECONDS" v={`${c.llm_timeout_seconds} s`} />
                <Row k="Max output tokens" env="LLM_MAX_OUTPUT_TOKENS" v={c.llm_max_output_tokens} />
                <Row k="Temperature" env="LLM_TEMPERATURE" v={c.llm_temperature} />
                <Row k="Price in / out (USD per M tokens)" env="LLM_PRICE_*" v={c.llm_price_input_per_mtok != null ? `${c.llm_price_input_per_mtok} / ${c.llm_price_output_per_mtok}` : null} />
                <Row k="Batch size" env="AI_BATCH_SIZE" v={c.ai_batch_size} />
                <Row k="Daily token budget" env="AI_DAILY_TOKEN_BUDGET" v={c.ai_daily_token_budget?.toLocaleString("en") ?? "unlimited"} />
              </dl>
            ) : null}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <div>
              <CardTitle className="flex items-center gap-2">
                <Cpu className="size-4 text-primary" /> Today
              </CardTitle>
              <CardDescription>Coverage of the AI pipeline and today&apos;s calls (UTC day).</CardDescription>
            </div>
            {s && <HealthPill status={s.problems.length ? "degraded" : "ok"} />}
          </CardHeader>
          <CardContent>
            {status.isLoading ? (
              <ListSkeleton rows={2} />
            ) : s ? (
              <dl className="grid grid-cols-2 gap-3 text-sm">
                {[
                  ["Calls", s.calls_today],
                  ["Errors", s.errors_today],
                  ["Tokens", s.tokens_today],
                  ["Cost", s.cost_today_usd != null ? money(s.cost_today_usd) : "—"],
                  ["Items", s.items_total],
                  ["With AI summary", s.items_with_ai_summary],
                  ["With embedding", s.items_with_embedding],
                  ["Failed analyses", s.failed_analyses],
                ].map(([k, v]) => (
                  <div key={String(k)} className="rounded-lg border p-3">
                    <dt className="text-xs text-muted-foreground">{k}</dt>
                    <dd className="tabular text-lg font-semibold">{typeof v === "number" ? v.toLocaleString("en") : v}</dd>
                  </div>
                ))}
                {s.problems.length > 0 && (
                  <ul className="col-span-2 list-disc space-y-1 pl-5 text-xs text-amber-700 dark:text-amber-300">
                    {s.problems.map((p) => (
                      <li key={p}>{p}</li>
                    ))}
                  </ul>
                )}
              </dl>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <div className="flex items-center justify-end gap-2 text-sm">
        <span className="text-muted-foreground">Window</span>
        <NativeSelect aria-label="Usage window" value={days} onChange={(e) => setDays(Number(e.target.value))} className="w-32">
          {[7, 30, 90].map((d) => (
            <option key={d} value={d}>
              {d} days
            </option>
          ))}
        </NativeSelect>
      </div>
      {usage.isLoading ? (
        <ListSkeleton rows={2} />
      ) : usage.isError ? (
        <ErrorState error={usage.error} onRetry={() => usage.refetch()} />
      ) : u ? (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard
              title="Tokens per day"
              description={`${u.ai_tokens_total.toLocaleString("en")} tokens in ${days} days${u.ai_daily_token_budget ? ` · budget ${u.ai_daily_token_budget.toLocaleString("en")}/day` : ""}`}
              table={{ columns: ["Day", "Tokens"], rows: u.ai_by_day.map((d) => [formatDay(d.day), d.tokens]) }}
            >
              <ActivityChart data={u.ai_by_day.map((d) => ({ day: d.day, count: d.tokens }))} unit="tokens" label="AI tokens per day" height={180} />
            </ChartCard>
            <ChartCard
              title="Provider errors per day"
              description="Failed LLM / embedding calls (timeouts, invalid output, HTTP errors)"
              table={{ columns: ["Day", "Errors"], rows: u.ai_by_day.map((d) => [formatDay(d.day), d.errors]) }}
            >
              <ActivityChart data={u.ai_by_day.map((d) => ({ day: d.day, count: d.errors }))} unit="errors" label="AI provider errors per day" height={180} />
            </ChartCard>
          </div>
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Usage by provider, model and purpose</CardTitle>
                <CardDescription>
                  Cost is estimated from LLM_PRICE_* settings ({u.ai_cost_total_usd != null ? `${money(u.ai_cost_total_usd)} total` : "not configured"}).
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {!u.ai_by_model.length ? (
                <p className="text-sm text-muted-foreground">No AI calls in this window.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[640px] text-sm">
                    <thead>
                      <tr className="border-b">
                        <Th>Provider / model</Th>
                        <Th>Purpose</Th>
                        <Th className="text-right">Calls</Th>
                        <Th className="text-right">Errors</Th>
                        <Th className="text-right">Input tokens</Th>
                        <Th className="text-right">Output tokens</Th>
                        <Th className="text-right">Cost</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {u.ai_by_model.map((r) => (
                        <tr key={`${r.provider}/${r.model}/${r.purpose}`} className="border-b last:border-0">
                          <Td className="font-medium">
                            {r.provider} / {r.model}
                          </Td>
                          <Td>{r.purpose}</Td>
                          <Td className="tabular text-right">{r.calls.toLocaleString("en")}</Td>
                          <Td className="tabular text-right">{r.errors.toLocaleString("en")}</Td>
                          <Td className="tabular text-right">{r.input_tokens.toLocaleString("en")}</Td>
                          <Td className="tabular text-right">{r.output_tokens.toLocaleString("en")}</Td>
                          <Td className="tabular text-right">{money(r.cost_usd)}</Td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}

export default function AdminAIPage() {
  return (
    <>
      <PageHeader title="AI providers & usage" description="Effective configuration, pipeline coverage, tokens, errors and cost." icon={Cpu} />
      <StaffGate what="AI administration">
        <AIAdmin />
      </StaffGate>
    </>
  );
}
