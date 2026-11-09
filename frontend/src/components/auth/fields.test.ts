import { describe, expect, it } from "vitest";

import { passwordProblem } from "@/components/auth/fields";

describe("passwordProblem (mirrors backend policy)", () => {
  it.each([
    ["short1A!", "12 characters"],
    ["alllowercaseletters", "3 of"],
    ["lowercase-and-symbols", "3 of"],
  ])("rejects %s", (pw, msg) => expect(passwordProblem(pw)).toContain(msg));

  it("accepts a strong password", () => expect(passwordProblem("Str0ng-Password!!")).toBeNull());
});
