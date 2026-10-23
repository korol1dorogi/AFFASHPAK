import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Schemas } from "@/api/client";
import { WizardPage } from "@/features/application-wizard/WizardPage";
import { mockApi, renderRoutes } from "@/test/utils";

const DRAFT: Schemas["ApplicationDetail"] = {
  id: 42,
  company_id: 3,
  need_type: "working_capital",
  purpose: "Закупка к сезону (демо)",
  product_code: null,
  requested_amount: "5300000.00",
  term_months: 12,
  invoice_amount: null,
  collateral_description: null,
  status: "draft",
  version: 1,
  prefill_source: "manual",
  available_actions: ["edit", "submit", "cancel"],
  created_at: "2026-10-22T09:00:00Z",
  submitted_at: null,
  status_changed_at: "2026-10-22T09:00:00Z",
  offer: null,
  open_info_requests: [],
  decision: null,
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("WizardPage — review (SRC7)", () => {
  it("the requested amount is the client's word", async () => {
    mockApi({
      "GET /api/applications/42": DRAFT,
      "GET /api/applications/42/documents": [],
      "GET /api/products": [],
      "GET /api/company/members": [],
    });
    renderRoutes(
      [{ path: "/app/applications/:id/edit/:step", element: <WizardPage /> }],
      "/app/applications/42/edit/review",
    );
    const amount = await screen.findByText("5 300 000 ₽");
    expect(amount.parentElement).toHaveTextContent("5 300 000 ₽со слов клиента на 12 мес");
  });
});
