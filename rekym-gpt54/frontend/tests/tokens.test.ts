import { describe, expect, it } from "vitest";

import { resolveApiBaseUrl, statusStyles } from "../src/theme/tokens";

describe("theme tokens", () => {
  it("exposes health status styles", () => {
    expect(statusStyles.ready).toContain("badge-primary");
  });

  it("uses the local API default when unset", () => {
    expect(resolveApiBaseUrl()).toBe("/api/v1");
  });
});