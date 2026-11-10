"use client";

import { Search, Users } from "lucide-react";
import { useState } from "react";

import { StaffGate, useIsStaff } from "@/components/admin/admin-shell";
import { Pagination } from "@/components/feed/pagination";
import { PageHeader } from "@/components/layout/page-header";
import { Td, Th } from "@/components/radar/shared";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/states/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { useAuth } from "@/lib/auth";
import { useAdminUsers, useRoles, useUpdateUser } from "@/lib/queries";
import type { Role } from "@/lib/types";
import { formatDateTime, titleCase } from "@/lib/utils";

const ROLE_HINT: Record<Role, string> = {
  admin: "Everything, including users, sources and the audit log",
  analyst: "Operations: ingestion, jobs, AI status and usage (read and retry)",
  user: "Read intelligence, personal briefings, bookmarks and notifications",
};

function UsersAdmin() {
  const { admin } = useIsStaff();
  const { user: me } = useAuth();
  const [q, setQ] = useState("");
  const [role, setRole] = useState<Role | "">("");
  const [active, setActive] = useState<"" | "true" | "false">("");
  const [page, setPage] = useState(1);
  const users = useAdminUsers({ q: q || undefined, role: role || undefined, is_active: active || undefined, page, page_size: 25 }, admin);
  const roles = useRoles(admin);
  const update = useUpdateUser();

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        {(roles.data ?? []).map((r) => (
          <Card key={r.name}>
            <CardContent className="pt-5">
              <div className="flex items-center justify-between">
                <p className="font-medium">{titleCase(r.name)}</p>
                <span className="tabular text-2xl font-semibold">{r.user_count}</span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{r.description ?? ROLE_HINT[r.name]}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Users</CardTitle>
            <CardDescription>
              Role and status changes are audited. You cannot demote or deactivate yourself, and the last active admin is
              protected. Deactivating a user signs them out everywhere.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 sm:grid-cols-[1fr_160px_160px]">
            <label className="relative">
              <span className="sr-only">Search users</span>
              <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" aria-hidden />
              <Input
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setPage(1);
                }}
                placeholder="Email or name"
                className="pl-8"
              />
            </label>
            <NativeSelect aria-label="Filter by role" value={role} onChange={(e) => (setRole(e.target.value as Role | ""), setPage(1))}>
              <option value="">All roles</option>
              <option value="admin">Admin</option>
              <option value="analyst">Analyst</option>
              <option value="user">User</option>
            </NativeSelect>
            <NativeSelect aria-label="Filter by status" value={active} onChange={(e) => (setActive(e.target.value as "" | "true" | "false"), setPage(1))}>
              <option value="">Any status</option>
              <option value="true">Active</option>
              <option value="false">Deactivated</option>
            </NativeSelect>
          </div>
          {users.isLoading ? (
            <ListSkeleton rows={3} />
          ) : users.isError ? (
            <ErrorState error={users.error} onRetry={() => users.refetch()} />
          ) : !users.data?.items.length ? (
            <EmptyState icon={Users} title="No users match" description="Try another search or filter." />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-sm">
                  <thead>
                    <tr className="border-b">
                      <Th>User</Th>
                      <Th>Role</Th>
                      <Th>Status</Th>
                      <Th>Last sign-in</Th>
                      <Th>Created</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.data.items.map((u) => {
                      const self = u.id === me?.id;
                      const busy = update.isPending && update.variables?.id === u.id;
                      return (
                        <tr key={u.id} className="border-b last:border-0">
                          <Td>
                            <p className="font-medium">{u.email}</p>
                            {u.full_name && <p className="text-xs text-muted-foreground">{u.full_name}</p>}
                          </Td>
                          <Td>
                            <NativeSelect
                              aria-label={`Role of ${u.email}`}
                              value={u.role}
                              disabled={self || busy}
                              onChange={(e) => update.mutate({ id: u.id, role: e.target.value })}
                              className="h-8 w-32"
                            >
                              <option value="admin">Admin</option>
                              <option value="analyst">Analyst</option>
                              <option value="user">User</option>
                            </NativeSelect>
                          </Td>
                          <Td>
                            <label className="inline-flex items-center gap-2">
                              <input
                                type="checkbox"
                                className="size-4 accent-[var(--primary)]"
                                checked={u.is_active}
                                disabled={self || busy}
                                onChange={(e) => update.mutate({ id: u.id, is_active: e.target.checked })}
                                aria-label={`${u.email} active`}
                              />
                              {u.is_active ? <Badge variant="secondary">Active</Badge> : <Badge variant="outline">Deactivated</Badge>}
                            </label>
                            {self && <p className="mt-1 text-[11px] text-muted-foreground">This is you</p>}
                          </Td>
                          <Td className="text-xs text-muted-foreground">{u.last_login_at ? formatDateTime(u.last_login_at) : "Never"}</Td>
                          <Td className="text-xs text-muted-foreground">{formatDateTime(u.created_at)}</Td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <Pagination page={users.data.page} pages={users.data.pages} total={users.data.total} pageSize={users.data.page_size} onChange={setPage} />
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function AdminUsersPage() {
  return (
    <>
      <PageHeader title="Users & roles" description="Manage accounts, roles and access." icon={Users} />
      <StaffGate adminOnly what="user management">
        <UsersAdmin />
      </StaffGate>
    </>
  );
}
