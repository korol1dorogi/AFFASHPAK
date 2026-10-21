import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Schemas } from "@/api/client";
import { safeNext } from "@/app/routes";
import { OfferCard } from "@/components/OfferCard";
import { ImprovementList, ReasonList } from "@/components/ReasonList";
import { StatusTimeline } from "@/components/StatusTimeline";

/** Stored text from clients and officers is data: it must render as text, never as markup. */
const PAYLOADS = [
  '<img src=x onerror="window.__xss=1">',
  '"><svg onload="window.__xss=1"></svg>',
  "<script>window.__xss=1</script>",
  "javascript:window.__xss=1",
];
// Lucide icons are inline svg too: look for what can run, not for any svg.
const ACTIVE = "script, iframe, img[src='x'], [onerror], [onload], a[href^='javascript:']";

describe("safeNext keeps sign-in redirects on this site", () => {
  it.each(["/app", "/app/applications/1", "/bank?status=offer"])("allows %s", (path) => {
    expect(safeNext(path)).toBe(path);
  });

  it.each([
    "//evil.example",
    "/\\evil.example",
    "\\\\evil.example",
    "https://evil.example",
    "javascript:alert(1)",
    "/app\n/evil",
    "",
    null,
  ])("rejects %j", (next) => {
    expect(safeNext(next)).toBeNull();
  });
});

describe("user and officer text renders as text", () => {
  it.each(PAYLOADS)("reasons, improvements and history: %s", (payload) => {
    const reason: Schemas["Reason"] = {
      metric: payload,
      value: null,
      threshold: null,
      passed: false,
      message: payload,
    };
    const event: Schemas["ApplicationEvent"] = {
      id: 1,
      kind: "info_requested",
      from_status: null,
      to_status: null,
      actor_kind: "bank",
      actor: { id: 1, full_name: payload },
      message: payload,
      is_internal: false,
      created_at: "2026-10-21T10:00:00Z",
    };
    const { container } = render(
      <>
        <ReasonList reasons={[reason]} />
        <ReasonList reasons={[reason]} variant="bank" />
        <ImprovementList items={[payload]} />
        <StatusTimeline events={[event]} />
      </>,
    );
    expect(container.querySelectorAll(ACTIVE)).toHaveLength(0);
    expect(container.textContent).toContain(payload);
  });

  it("offer card with a crafted product name", () => {
    const payload = PAYLOADS[0] as string;
    const offer = {
      id: 1,
      product: {
        code: "overdraft_basic",
        kind: "overdraft",
        name: payload,
        description: payload,
        rate_min: "0.20",
        rate_max: "0.32",
        term_min_months: 1,
        term_max_months: 12,
        amount_min: "100000.00",
        amount_max: "10000000.00",
        is_revolving: true,
        collateral_required: false,
        params: {},
        requirements: { min_business_age_months: 6, legal_forms: ["ip", "ooo"] },
        required_documents: [],
      },
      amount: "900000.00",
      requested_amount: "900000.00",
      term_months: 12,
      rate: "0.2000",
      monthly_payment: null,
      is_counteroffer: false,
      product_changed: true,
      status: "active",
      expires_at: "2026-11-20T10:00:00Z",
      reasons: [{ metric: "x", value: null, threshold: null, passed: false, message: payload }],
    } satisfies Schemas["Offer"];
    const { container } = render(<OfferCard offer={offer} actions={[]} />);
    expect(container.querySelectorAll(ACTIVE)).toHaveLength(0);
  });
});
