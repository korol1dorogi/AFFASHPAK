import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { BKI_CONSENT } from "@/texts";

describe("BKI_CONSENT", () => {
  it("has the same text version as the backend (a mismatch makes every submit a 400)", () => {
    const models = readFileSync(
      resolve(__dirname, "../../../backend/apps/applications/models.py"),
      "utf-8",
    );
    expect(models).toContain(`BKI_CONSENT_VERSION = "${BKI_CONSENT.version}"`);
  });
});
