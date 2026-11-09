"use client";

import { Loader2, Settings, X } from "lucide-react";
import { useTheme } from "next-themes";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/page-header";
import { ErrorState, ListSkeleton, SignInRequired } from "@/components/states/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { INTEREST_LABEL, SEVERITIES, SEVERITY_LABEL } from "@/lib/labels";
import { usePreferences, useUpdatePreferences } from "@/lib/queries";
import type { BriefingFrequency, Preferences, Severity } from "@/lib/types";

function TagInput({
  id,
  value,
  onChange,
  placeholder,
  validate,
}: {
  id: string;
  value: string[];
  onChange: (v: string[]) => void;
  placeholder: string;
  validate?: (v: string) => string | null;
}) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const add = () => {
    const v = draft.trim();
    if (!v) return;
    const err = validate?.(v) ?? null;
    if (err) return setError(err);
    if (!value.some((x) => x.toLowerCase() === v.toLowerCase())) onChange([...value, v]);
    setDraft("");
    setError(null);
  };
  return (
    <div>
      <div className="flex gap-2">
        <Input
          id={id}
          value={draft}
          placeholder={placeholder}
          maxLength={200}
          aria-invalid={!!error}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
        />
        <Button type="button" variant="outline" onClick={add}>
          Add
        </Button>
      </div>
      {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
      {value.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {value.map((v) => (
            <li key={v} className="inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-1 text-xs">
              {v}
              <button type="button" aria-label={`Remove ${v}`} onClick={() => onChange(value.filter((x) => x !== v))}>
                <X className="size-3" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PreferencesForm({ initial }: { initial: Preferences }) {
  const [p, setP] = useState<Preferences>(initial);
  const save = useUpdatePreferences();
  const timezones = useMemo(() => {
    try {
      return Intl.supportedValuesOf("timeZone");
    } catch {
      return ["UTC"];
    }
  }, []);
  const set = <K extends keyof Preferences>(k: K, v: Preferences[K]) => setP((prev) => ({ ...prev, [k]: v }));

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate({
          interests: p.interests,
          followed_technologies: p.followed_technologies,
          followed_repositories: p.followed_repositories,
          followed_providers: p.followed_providers,
          min_notification_severity: p.min_notification_severity,
          briefing_frequency: p.briefing_frequency,
          briefing_hour: p.briefing_hour,
          timezone: p.timezone,
        });
      }}
      className="space-y-6"
    >
      <fieldset>
        <legend className="text-sm font-medium">Interests</legend>
        <p className="mb-3 text-xs text-muted-foreground">Used to personalise briefings and rank items.</p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(INTEREST_LABEL).map(([slug, label]) => (
            <label key={slug} className="flex cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2 text-sm hover:bg-accent/50">
              <Checkbox
                checked={p.interests.includes(slug)}
                onCheckedChange={(c) =>
                  set("interests", c ? [...p.interests, slug] : p.interests.filter((x) => x !== slug))
                }
              />
              {label}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="grid gap-5 md:grid-cols-3">
        <div className="space-y-2">
          <Label htmlFor="tech">Followed technologies</Label>
          <TagInput id="tech" value={p.followed_technologies} onChange={(v) => set("followed_technologies", v)} placeholder="e.g. vLLM" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="repos">Followed GitHub repositories</Label>
          <TagInput
            id="repos"
            value={p.followed_repositories}
            onChange={(v) => set("followed_repositories", v)}
            placeholder="owner/name"
            validate={(v) => (/^[\w.-]+\/[\w.-]+$/.test(v) ? null : "Use the owner/name format")}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="providers">Followed AI providers</Label>
          <TagInput id="providers" value={p.followed_providers} onChange={(v) => set("followed_providers", v)} placeholder="e.g. Mistral AI" />
        </div>
      </div>

      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-2">
          <Label htmlFor="sev">Notify me from severity</Label>
          <NativeSelect id="sev" value={p.min_notification_severity} onChange={(e) => set("min_notification_severity", e.target.value as Severity)}>
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {SEVERITY_LABEL[s]} and above
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="space-y-2">
          <Label htmlFor="freq">Briefing frequency</Label>
          <NativeSelect id="freq" value={p.briefing_frequency} onChange={(e) => set("briefing_frequency", e.target.value as BriefingFrequency)}>
            <option value="daily">Daily</option>
            <option value="weekdays">Weekdays</option>
            <option value="weekly">Weekly</option>
            <option value="off">Off</option>
          </NativeSelect>
        </div>
        <div className="space-y-2">
          <Label htmlFor="hour">Delivery time</Label>
          <NativeSelect id="hour" value={p.briefing_hour} onChange={(e) => set("briefing_hour", Number(e.target.value))}>
            {Array.from({ length: 24 }, (_, h) => (
              <option key={h} value={h}>
                {String(h).padStart(2, "0")}:00
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="space-y-2">
          <Label htmlFor="tz">Timezone</Label>
          <NativeSelect id="tz" value={p.timezone} onChange={(e) => set("timezone", e.target.value)}>
            {!timezones.includes(p.timezone) && <option value={p.timezone}>{p.timezone}</option>}
            {timezones.map((tz) => (
              <option key={tz} value={tz}>
                {tz}
              </option>
            ))}
          </NativeSelect>
        </div>
      </div>

      <Button type="submit" variant="brand" disabled={save.isPending}>
        {save.isPending && <Loader2 className="animate-spin" />} Save preferences
      </Button>
    </form>
  );
}

function ProfileCard() {
  const { user, reload } = useAuth();
  const [name, setName] = useState(user?.full_name ?? "");
  const [saving, setSaving] = useState(false);
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Profile</CardTitle>
          <CardDescription>{user?.email}</CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <form
          className="flex flex-col gap-3 sm:flex-row sm:items-end"
          onSubmit={async (e) => {
            e.preventDefault();
            setSaving(true);
            try {
              await api.patch("/auth/me", { full_name: name.trim() || null });
              await reload();
              toast.success("Profile updated");
            } catch (err) {
              toast.error(errorMessage(err));
            } finally {
              setSaving(false);
            }
          }}
        >
          <div className="flex-1 space-y-2">
            <Label htmlFor="name">Full name</Label>
            <Input id="name" value={name} maxLength={200} onChange={(e) => setName(e.target.value)} />
          </div>
          <Button type="submit" variant="outline" disabled={saving}>
            {saving && <Loader2 className="animate-spin" />} Save
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function PasswordCard() {
  const { logout } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [saving, setSaving] = useState(false);
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Password</CardTitle>
          <CardDescription>At least 12 characters with 3 of: lowercase, uppercase, digit, symbol. Signs out all sessions.</CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
          onSubmit={async (e) => {
            e.preventDefault();
            setSaving(true);
            try {
              await api.post("/auth/change-password", { current_password: current, new_password: next });
              toast.success("Password changed — please sign in again");
              await logout();
            } catch (err) {
              toast.error(errorMessage(err));
            } finally {
              setSaving(false);
            }
          }}
        >
          <div className="space-y-2">
            <Label htmlFor="cur">Current password</Label>
            <Input id="cur" type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="new">New password</Label>
            <Input id="new" type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={next} onChange={(e) => setNext(e.target.value)} />
          </div>
          <Button type="submit" variant="outline" disabled={saving}>
            {saving && <Loader2 className="animate-spin" />} Change
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function AppearanceCard() {
  const { theme, setTheme } = useTheme();
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Appearance</CardTitle>
          <CardDescription>Stored in this browser.</CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex gap-2" role="radiogroup" aria-label="Theme">
          {(["dark", "light", "system"] as const).map((t) => (
            <Button key={t} role="radio" aria-checked={theme === t} variant={theme === t ? "default" : "outline"} size="sm" onClick={() => setTheme(t)}>
              {t[0]!.toUpperCase() + t.slice(1)}
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export default function SettingsPage() {
  const { status } = useAuth();
  const prefs = usePreferences();

  return (
    <>
      <PageHeader title="Settings" description="Your profile, security, interests and notification preferences." icon={Settings} />
      {status === "loading" ? (
        <ListSkeleton rows={2} />
      ) : status === "anonymous" ? (
        <div className="space-y-4">
          <AppearanceCard />
          <SignInRequired what="settings" />
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <ProfileCard />
            <AppearanceCard />
          </div>
          <PasswordCard />
          <Card id="preferences" className="scroll-mt-20">
            <CardHeader>
              <div>
                <CardTitle>Preferences</CardTitle>
                <CardDescription>Personalisation for briefings and alerts.</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {prefs.isLoading ? (
                <ListSkeleton rows={1} />
              ) : prefs.isError ? (
                <ErrorState error={prefs.error} onRetry={() => prefs.refetch()} />
              ) : prefs.data ? (
                <PreferencesForm initial={prefs.data} />
              ) : null}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
