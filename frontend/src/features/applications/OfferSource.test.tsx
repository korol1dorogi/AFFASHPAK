import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Schemas } from "@/api/client";
import { ApplicationPage } from "@/features/applications/ApplicationPage";
import { SignPage } from "@/features/signing/SignPage";
import { mockApi, renderRoutes } from "@/test/utils";

/** Persona 3 (демо): asked 5.3 mln, the counteroffer is 2 009 314 ₽ (scenario 3). */
const OFFER = {
  id: 5,
  product: {
    code: "working_capital_loan_basic",
    kind: "working_capital_loan",
    name: "Кредит на пополнение оборотных средств (демо)",
    description: "",
    rate_min: "0.1900",
    rate_max: "0.2800",
    term_min_months: 3,
    term_max_months: 24,
    amount_min: "300000.00",
    amount_max: "30000000.00",
    is_revolving: false,
    collateral_required: false,
    params: { min_dscr: "1.25" },
    requirements: { min_business_age_months: 12, legal_forms: ["ip", "ooo"] },
    required_documents: [],
  },
  amount: "2009314.00",
  requested_amount: "5300000.00",
  term_months: 12,
  rate: "0.2400",
  monthly_payment: "189999.92",
  is_counteroffer: true,
  product_changed: false,
  status: "active",
  expires_at: "2026-10-29T12:00:00Z",
  reasons: [],
} satisfies Schemas["Offer"];

function decision(decidedBy: "auto" | "officer"): Schemas["Decision"] {
  return {
    id: 9,
    application_id: 42,
    outcome: "counteroffer",
    decided_by: decidedBy,
    is_preliminary: decidedBy === "auto",
    grade: "B",
    policy_version: "2026.10-v1",
    reasons: [],
    improvements: [],
    comment: null,
    created_at: "2026-10-22T09:06:00Z",
  };
}

function detail(
  decidedBy: "auto" | "officer",
  changes: Partial<Schemas["ApplicationDetail"]> = {},
): Schemas["ApplicationDetail"] {
  return {
    id: 42,
    company_id: 3,
    need_type: "working_capital",
    purpose: "Закупка к сезону (демо)",
    product_code: "working_capital_loan_basic",
    requested_amount: "5300000.00",
    term_months: 12,
    invoice_amount: null,
    collateral_description: null,
    status: "offer",
    version: 4,
    prefill_source: "recommendation",
    available_actions: [],
    created_at: "2026-10-22T09:00:00Z",
    submitted_at: "2026-10-22T09:05:00Z",
    status_changed_at: "2026-10-22T09:06:00Z",
    offer: OFFER,
    open_info_requests: [],
    decision: decision(decidedBy),
    ...changes,
  };
}

function stub(page: Schemas["ApplicationDetail"]) {
  mockApi({
    "GET /api/applications/42": page,
    "GET /api/applications/42/events": [],
    "GET /api/applications/42/documents": [],
    "GET /api/products": [OFFER.product],
  });
}

/** The label right after the amount: «2 009 314 ₽» and its SourceTag share one parent. */
const amountLine = (scope: HTMLElement, text: string) =>
  within(scope).getAllByText(text)[0]?.parentElement;

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("where the offer's amounts come from (SRC7)", () => {
  it("an automatic counteroffer: counted amount and payment, the client's request", async () => {
    stub(detail("auto"));
    renderRoutes(
      [{ path: "/app/applications/:id", element: <ApplicationPage /> }],
      "/app/applications/42",
    );
    const offer = await screen.findByRole("article", { name: "Предложение банка" });
    expect(amountLine(offer, "2 009 314 ₽")).toHaveTextContent("2 009 314 ₽расчёт");
    expect(within(offer).getByText("Запрошено: 5 300 000 ₽")).toHaveTextContent(
      "Запрошено: 5 300 000 ₽вы указали",
    );
    expect(amountLine(offer, "189 999,92 ₽")).toHaveTextContent("189 999,92 ₽расчёт");
  });

  it("an officer's counteroffer: the amount is the bank's decision, the payment still counted", async () => {
    stub(detail("officer"));
    renderRoutes(
      [{ path: "/app/applications/:id", element: <ApplicationPage /> }],
      "/app/applications/42",
    );
    const offer = await screen.findByRole("article", { name: "Предложение банка" });
    expect(amountLine(offer, "2 009 314 ₽")).toHaveTextContent("2 009 314 ₽решение банка");
    expect(amountLine(offer, "189 999,92 ₽")).toHaveTextContent("189 999,92 ₽расчёт");
  });

  it("signing shows the amount with the same label", async () => {
    stub(detail("officer", { status: "signing", available_actions: ["sign"] }));
    renderRoutes(
      [{ path: "/app/applications/:id/sign", element: <SignPage /> }],
      "/app/applications/42/sign",
    );
    await screen.findByRole("heading", { name: "Подписание договора" });
    expect(amountLine(document.body, "2 009 314 ₽")).toHaveTextContent("2 009 314 ₽решение банка");
  });
});
