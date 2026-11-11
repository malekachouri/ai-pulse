import { request, type FullConfig } from "@playwright/test";

import { ACCOUNTS } from "./tests/helpers";

/** Creates the regular test account (the admin is created by scripts/e2e.sh with the CLI). */
export default async function globalSetup(config: FullConfig): Promise<void> {
  const baseURL = config.projects[0].use.baseURL as string;
  const api = await request.newContext({ baseURL });
  const r = await api.post("/api/v1/auth/register", {
    data: { email: ACCOUNTS.user.email, password: ACCOUNTS.user.password, full_name: "E2E Reader" },
  });
  if (![201, 409].includes(r.status())) throw new Error(`register test user: HTTP ${r.status()} ${await r.text()}`);
  await api.dispose();
}
