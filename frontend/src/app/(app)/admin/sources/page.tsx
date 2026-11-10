"use client";

import { Loader2, Plus, Rss, Save, Trash2, X } from "lucide-react";
import { useMemo, useState } from "react";

import { StaffGate, useIsStaff } from "@/components/admin/admin-shell";
import { PageHeader } from "@/components/layout/page-header";
import { Td, Th } from "@/components/radar/shared";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { useAdminSources, useConnectors, useSourceMutations } from "@/lib/queries";
import type { AdminSource, ItemType } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

const SOURCE_TYPES = ["rss", "api", "github", "status_page", "scrape"];
const ITEM_TYPES: ItemType[] = ["news", "model_release", "tool", "research", "github_repo", "github_issue", "bug", "vulnerability", "incident", "devops"];

/** Parses the JSON config textarea; returns an error message instead of throwing. */
function parseConfig(text: string): { value?: Record<string, unknown>; error?: string } {
  if (!text.trim()) return { value: {} };
  try {
    const v = JSON.parse(text) as unknown;
    if (typeof v !== "object" || v === null || Array.isArray(v)) return { error: "Config must be a JSON object" };
    return { value: v as Record<string, unknown> };
  } catch (e) {
    return { error: `Invalid JSON: ${(e as Error).message}` };
  }
}

function SourceForm({ initial, onDone }: { initial?: AdminSource; onDone: () => void }) {
  const connectors = useConnectors(true);
  const { create, update } = useSourceMutations();
  const editing = Boolean(initial);
  const [f, setF] = useState({
    slug: initial?.slug ?? "",
    name: initial?.name ?? "",
    connector: initial?.connector ?? "rss",
    source_type: initial?.source_type ?? "rss",
    url: initial?.url ?? "",
    homepage_url: initial?.homepage_url ?? "",
    default_item_type: (initial?.default_item_type ?? "news") as ItemType,
    is_official: initial?.is_official ?? true,
    reliability: initial?.reliability ?? 0.8,
    poll_interval_minutes: initial?.poll_interval_minutes ?? 60,
    config: JSON.stringify(initial?.config ?? {}, null, 2),
    reset_checkpoint: false,
  });
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));
  const cfg = parseConfig(f.config);
  const schema = connectors.data?.find((c) => c.key === f.connector);
  const busy = create.isPending || update.isPending;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (cfg.error) return;
    const common = {
      name: f.name,
      url: f.url,
      homepage_url: f.homepage_url || null,
      is_official: f.is_official,
      reliability: Number(f.reliability),
      poll_interval_minutes: Number(f.poll_interval_minutes),
      config: cfg.value,
    };
    if (initial)
      update.mutate({ id: initial.id, ...common, reset_checkpoint: f.reset_checkpoint }, { onSuccess: onDone });
    else
      create.mutate(
        { ...common, slug: f.slug, connector: f.connector, source_type: f.source_type, default_item_type: f.default_item_type },
        { onSuccess: onDone },
      );
  };

  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl border p-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div className="space-y-1.5">
          <Label htmlFor="s-slug">Slug</Label>
          <Input id="s-slug" value={f.slug} disabled={editing} onChange={(e) => set("slug", e.target.value)} placeholder="vendor-blog" pattern="[a-z0-9-]+" required />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="s-name">Name</Label>
          <Input id="s-name" value={f.name} onChange={(e) => set("name", e.target.value)} required minLength={2} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="s-conn">Connector</Label>
          <NativeSelect id="s-conn" value={f.connector} disabled={editing} onChange={(e) => set("connector", e.target.value)}>
            {(connectors.data ?? [{ key: f.connector, description: "", config_schema: {} }]).map((c) => (
              <option key={c.key} value={c.key}>
                {c.key}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="s-type">Source type</Label>
          <NativeSelect id="s-type" value={f.source_type} disabled={editing} onChange={(e) => set("source_type", e.target.value)}>
            {SOURCE_TYPES.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </NativeSelect>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="s-item">Default item type</Label>
          <NativeSelect id="s-item" value={f.default_item_type} disabled={editing} onChange={(e) => set("default_item_type", e.target.value as ItemType)}>
            {ITEM_TYPES.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </NativeSelect>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="s-int">Poll interval (minutes)</Label>
          <Input id="s-int" type="number" min={5} max={10080} value={f.poll_interval_minutes} onChange={(e) => set("poll_interval_minutes", Number(e.target.value))} />
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="s-url">Feed / API URL (official source)</Label>
          <Input id="s-url" type="url" value={f.url} onChange={(e) => set("url", e.target.value)} placeholder="https://…" required />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="s-rel">Reliability (0–1)</Label>
          <Input id="s-rel" type="number" step="0.05" min={0} max={1} value={f.reliability} onChange={(e) => set("reliability", Number(e.target.value))} />
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="s-home">Homepage URL (optional)</Label>
          <Input id="s-home" type="url" value={f.homepage_url} onChange={(e) => set("homepage_url", e.target.value)} />
        </div>
        <label className="flex items-center gap-2 self-end pb-2 text-sm">
          <input type="checkbox" className="size-4" checked={f.is_official} onChange={(e) => set("is_official", e.target.checked)} />
          Official source
        </label>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="s-cfg">Connector options (JSON)</Label>
        <textarea
          id="s-cfg"
          value={f.config}
          onChange={(e) => set("config", e.target.value)}
          rows={5}
          spellCheck={false}
          aria-invalid={Boolean(cfg.error)}
          className="w-full rounded-md border bg-transparent px-3 py-2 font-mono text-xs"
        />
        {cfg.error ? (
          <p className="text-xs text-destructive">{cfg.error}</p>
        ) : schema ? (
          <details className="text-xs text-muted-foreground">
            <summary className="cursor-pointer">Options accepted by {schema.key} (validated server-side)</summary>
            <p className="mt-1">{schema.description}</p>
            <pre className="mt-1 max-h-48 overflow-auto rounded bg-muted p-2">{JSON.stringify((schema.config_schema as { properties?: unknown }).properties ?? schema.config_schema, null, 2)}</pre>
          </details>
        ) : null}
      </div>
      {editing && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4" checked={f.reset_checkpoint} onChange={(e) => set("reset_checkpoint", e.target.checked)} />
          Reset checkpoint (next run re-reads the source from the start; duplicates are still prevented)
        </label>
      )}
      <div className="flex gap-2">
        <Button type="submit" variant="brand" disabled={busy || Boolean(cfg.error)}>
          {busy ? <Loader2 className="animate-spin" /> : <Save />} {editing ? "Save" : "Create source"}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          <X /> Cancel
        </Button>
      </div>
    </form>
  );
}

function Sources() {
  const { admin } = useIsStaff();
  const q = useAdminSources(admin);
  const { update, remove } = useSourceMutations();
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [filter, setFilter] = useState("");
  const rows = useMemo(
    () => (q.data ?? []).filter((s) => !filter || `${s.slug} ${s.name} ${s.connector}`.toLowerCase().includes(filter.toLowerCase())),
    [q.data, filter],
  );
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Sources</CardTitle>
          <CardDescription>
            Official sources only. Connector options are validated before saving; every change is audited. Sources that already
            collected items can be disabled but not deleted, so their items keep a valid origin.
          </CardDescription>
        </div>
        {editing !== "new" && (
          <Button onClick={() => setEditing("new")}>
            <Plus /> Add source
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {editing === "new" && <SourceForm onDone={() => setEditing(null)} />}
        <Input aria-label="Filter sources" placeholder="Filter by name, slug or connector" value={filter} onChange={(e) => setFilter(e.target.value)} className="max-w-sm" />
        {q.isLoading ? (
          <ListSkeleton rows={4} />
        ) : q.isError ? (
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        ) : !rows.length ? (
          <EmptyState icon={Rss} title="No sources" description="Add an official source to start collecting." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b">
                  <Th>Source</Th>
                  <Th>Connector</Th>
                  <Th className="text-right">Interval</Th>
                  <Th>Last success</Th>
                  <Th>Failures</Th>
                  <Th>Enabled</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {rows.map((s) =>
                  editing === s.id ? (
                    <tr key={s.id}>
                      <td colSpan={7} className="py-2">
                        <SourceForm initial={s} onDone={() => setEditing(null)} />
                      </td>
                    </tr>
                  ) : (
                    <tr key={s.id} className="border-b last:border-0">
                      <Td>
                        <p className="font-medium">
                          {s.name} {s.is_official && <Badge variant="secondary">official</Badge>}
                        </p>
                        <p className="break-all text-xs text-muted-foreground">{s.url}</p>
                      </Td>
                      <Td>
                        <code className="text-xs">{s.connector}</code>
                      </Td>
                      <Td className="tabular text-right">{s.poll_interval_minutes} min</Td>
                      <Td className="text-xs text-muted-foreground">{s.last_success_at ? formatDateTime(s.last_success_at) : "never"}</Td>
                      <Td>
                        {s.consecutive_failures ? (
                          <span className="font-semibold text-sev-critical" title={s.last_error ?? undefined}>
                            {s.consecutive_failures}
                          </span>
                        ) : (
                          "0"
                        )}
                      </Td>
                      <Td>
                        <input
                          type="checkbox"
                          className="size-4"
                          checked={s.enabled}
                          aria-label={`${s.name} enabled`}
                          disabled={update.isPending && update.variables?.id === s.id}
                          onChange={(e) => update.mutate({ id: s.id, enabled: e.target.checked })}
                        />
                      </Td>
                      <Td className="whitespace-nowrap text-right">
                        <Button size="sm" variant="ghost" onClick={() => setEditing(s.id)}>
                          Edit
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-muted-foreground hover:text-destructive"
                          aria-label={`Delete ${s.name}`}
                          disabled={remove.isPending}
                          onClick={() => {
                            if (window.confirm(`Delete source "${s.name}"? This cannot be undone.`)) remove.mutate(s.id);
                          }}
                        >
                          <Trash2 />
                        </Button>
                      </Td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function AdminSourcesPage() {
  return (
    <>
      <PageHeader title="Sources" description="Create, configure, enable or remove data sources." icon={Rss} />
      <StaffGate adminOnly what="source management">
        <Sources />
      </StaffGate>
    </>
  );
}
