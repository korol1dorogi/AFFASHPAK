import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Schemas } from "@/api/client";
import { SignPage } from "@/features/signing/SignPage";
import { mockApi, renderRoutes } from "@/test/utils";

function signing(actions: Schemas["ApplicationAction"][]): Schemas["ApplicationDetail"] {
  return {
    id: 42,
    company_id: 3,
    need_type: "working_capital",
    purpose: "Закупка к сезону (демо)",
    product_code: "working_capital_loan_basic",
    requested_amount: "2009314.00",
    term_months: 12,
    invoice_amount: null,
    collateral_description: null,
    status: "signing",
    version: 5,
    prefill_source: "recommendation",
    available_actions: actions,
    created_at: "2026-10-22T09:00:00Z",
    submitted_at: "2026-10-22T09:05:00Z",
    status_changed_at: "2026-10-22T09:10:00Z",
    offer: null,
    open_info_requests: [],
    decision: null,
  };
}

function open(detail: Schemas["ApplicationDetail"]) {
  const fetchMock = mockApi({
    "GET /api/applications/42": detail,
    "POST /api/applications/42/cancel": { ...detail, status: "cancelled", available_actions: [] },
  });
  renderRoutes(
    [
      { path: "/app/applications/:id/sign", element: <SignPage /> },
      { path: "/app/applications/:id", element: <p>Страница заявки</p> },
    ],
    "/app/applications/42/sign",
  );
  return fetchMock;
}

const cancelCalls = (fetchMock: ReturnType<typeof mockApi>) =>
  fetchMock.mock.calls.filter(
    ([request]) => new URL((request as Request).url).pathname === "/api/applications/42/cancel",
  );

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("SignPage — walking away before signing (fix 3.2)", () => {
  it("asks first, then cancels and goes back to the application", async () => {
    const fetchMock = open(signing(["sign", "cancel"]));
    fireEvent.click(await screen.findByRole("button", { name: "Отказаться и отозвать заявку" }));

    const dialog = screen.getByRole("dialog", { name: "Отказаться от договора?" });
    expect(dialog).toHaveTextContent("Договор не будет подписан, заявка закроется.");
    expect(cancelCalls(fetchMock)).toHaveLength(0); // nothing happens until confirmed

    fireEvent.click(within(dialog).getByRole("button", { name: "Отозвать заявку" }));
    expect(await screen.findByText("Страница заявки")).toBeInTheDocument();
    expect(cancelCalls(fetchMock)).toHaveLength(1);
  });

  it("«Вернуться к подписанию» keeps the application", async () => {
    const fetchMock = open(signing(["sign", "cancel"]));
    fireEvent.click(await screen.findByRole("button", { name: "Отказаться и отозвать заявку" }));
    fireEvent.click(screen.getByRole("button", { name: "Вернуться к подписанию" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Подписание договора" })).toBeInTheDocument();
    expect(cancelCalls(fetchMock)).toHaveLength(0);
  });

  it("without cancel in available_actions there is no button", async () => {
    open(signing(["sign"]));
    await screen.findByRole("heading", { name: "Подписание договора" });
    expect(
      screen.queryByRole("button", { name: "Отказаться и отозвать заявку" }),
    ).not.toBeInTheDocument();
  });
});
