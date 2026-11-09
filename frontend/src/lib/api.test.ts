import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch, ApiError, buildQuery, errorMessage, getAccessToken, setAccessToken } from "@/lib/api";
import { safeUrl } from "@/lib/utils";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => {
  vi.restoreAllMocks();
  setAccessToken(null);
});

describe("buildQuery", () => {
  it("repeats array params and skips empty values", () => {
    expect(buildQuery({ a: ["x", "y"], b: "", c: undefined, d: 0, e: false })).toBe("?a=x&a=y&d=0&e=false");
    expect(buildQuery({})).toBe("");
  });
});

describe("apiFetch", () => {
  it("parses the backend error envelope", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(json(404, { error: { code: "not_found", message: "Article not found" } }));
    await expect(apiFetch("/news/x")).rejects.toMatchObject({ status: 404, code: "not_found", message: "Article not found" });
  });

  it("refreshes once on 401 and retries with the new token", async () => {
    setAccessToken("old");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(json(401, { error: { code: "unauthorized", message: "expired" } }))
      .mockResolvedValueOnce(json(200, { access_token: "new" }))
      .mockResolvedValueOnce(json(200, { ok: true }));
    await expect(apiFetch("/bookmarks")).resolves.toEqual({ ok: true });
    expect(getAccessToken()).toBe("new");
    const lastHeaders = fetchMock.mock.calls[2]![1]!.headers as Headers;
    expect(lastHeaders.get("Authorization")).toBe("Bearer new");
  });

  it("reports network failures clearly", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("fetch failed"));
    await expect(apiFetch("/news")).rejects.toMatchObject({ code: "network_error" });
  });
});

describe("errorMessage", () => {
  it("prefers the first validation detail", () => {
    const err = new ApiError(422, "validation_error", "Request validation failed", [{ msg: "Value error, Unknown timezone 'X'" }]);
    expect(errorMessage(err)).toBe("Unknown timezone 'X'");
  });
});

describe("safeUrl", () => {
  it("only allows http(s) links", () => {
    expect(safeUrl("https://nvd.nist.gov/vuln/detail/CVE-2026-1")).toBe("https://nvd.nist.gov/vuln/detail/CVE-2026-1");
    expect(safeUrl("javascript:alert(1)")).toBeUndefined();
    expect(safeUrl("data:text/html,hi")).toBeUndefined();
    expect(safeUrl("not a url")).toBeUndefined();
  });
});
